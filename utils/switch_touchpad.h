#pragma once

// 触摸板开关（对应 utils/switch_touchpad.py）
//
// 通过 pwsh.exe 查询/枚举 PnP 触摸板设备（Get-PnpDevice），切换动作用
// ShellExecuteW "runas" 提权运行 tools/Set-PnpDeviceState.ps1。

#include <QList>
#include <QString>
#include <QStringList>

#include <optional>

namespace SwitchTouchpad {

struct DeviceInfo
{
    QString friendlyName;
    QString instanceId;
    int configManagerErrorCode = -1;
};

// 枚举触摸板设备（FriendlyName 匹配 Touchpad|Touch Pad|触摸板）
QList<DeviceInfo> getTouchpadDevices();

// 读取当前触摸板启用状态：
// true=已启用 / false=已禁用 / 无值=无法确定（未找到设备或查询失败）
std::optional<bool> getTouchpadStatus();

// 以管理员权限运行 PowerShell 脚本（触发 UAC）
bool runPsAsAdmin(const QString& scriptPath, const QString& arguments);

// 对所有触摸板设备执行启用/禁用（每个设备一次 UAC 提权请求）
void runSwitchTouchpad(bool enable);

} // namespace SwitchTouchpad
