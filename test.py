# TODO: 鼠标移动到组件后自动获取选中文本

import time
import uiautomation as auto

def get_selected_text():
    try:
        # 获取当前获得焦点的控件
        control = auto.GetFocusedControl()
        if not control:
            return ""
        
        # 获取控件的文本模式
        pattern = control.GetTextPattern()
        if pattern:
            selection = pattern.GetSelection()
            if selection:
                # 获取选中区域的文本内容（-1 表示获取完整文本）
                return selection[0].GetText(-1)
    except Exception:
        # 忽略切换焦点或不受支持控件抛出的异常
        pass
    return ""

if __name__ == "__main__":
    print("开始轮询获取选中文本（按 Ctrl+C 退出）...\n")
    
    try:
        while True:
            selected_text = get_selected_text()
            timestamp = time.strftime("%H:%M:%S")
            
            if selected_text:
                print(f"[{timestamp}] 选中内容: {selected_text}")
            else:
                print(f"[{timestamp}] 未检测到选中内容")
                
            time.sleep(1)  # 间隔 1 秒
    except KeyboardInterrupt:
        print("\n程序已停止。")