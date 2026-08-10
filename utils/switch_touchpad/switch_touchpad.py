import ctypes
import json
import subprocess
from resources.constants import root_dir

def get_touchpad_devices():
    # 1. 编写 PowerShell 脚本，最后加上 | ConvertTo-Json 转化为 JSON 格式
    powershell_script = """
    Get-PnpDevice | Where-Object {
        $_.FriendlyName -match "Touchpad|Touch Pad|触摸板"
    } | Select-Object FriendlyName, InstanceId | ConvertTo-Json
    """

    # 2. 构造执行命令
    # -NoProfile: 不加载用户配置，加快启动速度
    # -Command: 执行后面的脚本字符串
    command = ["pwsh.exe", "-NoProfile", "-Command", powershell_script]

    try:
        # 3. 运行命令并捕获输出
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # 将输出作为字符串处理（自动解码）
            check=True,  # 如果脚本报错则抛出异常
        )

        # 4. 解析 JSON 数据
        if not result.stdout.strip():
            print("未找到匹配的触摸板设备。")
            return []

        # 将 JSON 字符串转换为 Python 的列表/字典
        devices = json.loads(result.stdout)

        # 兼容处理：如果只找到一个设备，ConvertTo-Json 返回的是单个字典，而不是列表
        if isinstance(devices, dict):
            devices = [devices]

        return devices

    except subprocess.CalledProcessError as e:
        print(f"PowerShell 脚本执行失败: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return []

def run_ps_as_admin(script_path, arguments=""):
    """
    以管理员权限运行指定的 PowerShell 脚本
    :param script_path: PowerShell 脚本的绝对路径
    :param arguments: 传递给脚本的参数字符串
    """
    # 确保路径中的斜杠在 Windows 下正常工作
    script_path = script_path.replace('/', '\\')
    
    # 构建 PowerShell 的启动参数
    # -NoProfile: 不加载用户配置文件
    # -ExecutionPolicy Bypass: 绕过脚本执行策略限制，防止因策略问题无法运行
    # -File: 指定运行的脚本文件
    ps_args = f"-NoProfile -ExecutionPolicy Bypass -File \"{script_path}\" {arguments}"
    
    print(f"[+] 正在尝试以管理员权限启动 PowerShell 脚本: {script_path}")
    
    # 使用 ShellExecuteW 触发 UAC 提权
    # 'runas' 是触发管理员权限的关键
    retval = ctypes.windll.shell32.ShellExecuteW(
        None,          # 父窗口句柄
        "runas",       # 操作类型：以管理员身份运行
        "pwsh.exe", # 要执行的程序
        ps_args,       # 传递给程序的参数
        None,          # 工作目录 (None 表示当前目录)
        1              # SW_SHOWNORMAL: 显示窗口
    )
    
    # ShellExecuteW 返回值大于 32 表示执行成功
    if retval > 32:
        print("[+] 提权请求已发送，请在 UAC 弹窗中点击‘是’。")
        return True
    else:
        print(f"[-] 启动失败，错误码: {retval}")
        return False

def run_switch_touchpad(enable=True):

    current_dir = root_dir / 'utils' / 'switch_touchpad'
    target_script = current_dir / "switch.ps1"
    # 将 Path 对象显式转换为字符串
    script_path_str = str(target_script)
    action_value = "Enable" if enable else "Disable"

    touchpad_list = get_touchpad_devices()
    print(f"找到 {len(touchpad_list)} 个相关设备：\n")
    for device in touchpad_list:

        device_id = device.get('InstanceId')
        if not device_id:
            continue

        print(f"设备名称: {device.get('FriendlyName')}")
        print(f"实例 ID : {device_id}")
        print("-" * 40)

        # 构建符合 PowerShell 规范的参数字符串 (-参数名 参数值)
        ps_arguments = f'-Action "{action_value}" -InstanceId "{device_id}"'
        run_ps_as_admin(script_path_str, arguments=ps_arguments)

# --- 示例调用 ---
if __name__ == "__main__":
    run_switch_touchpad(True)