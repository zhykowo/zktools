import time
import utils.clipboard_monitor as clipboard_monitor

class _textManager:
    def __init__(self):
        import uiautomation as auto
        self.auto = auto

        self.selected_text = ''
        self.selection_time = time.perf_counter()

        self.clipboard_text = ''
        self.copy_time = time.perf_counter()

        clipboard_monitor.get().cbChanged.connect(self.get_clipboard_text)
        
    def get_selected_text(self):
        try:
            # 获取当前获得焦点的控件
            control = self.auto.GetFocusedControl()
            if not control:
                print('error: not control')
                return ""

            # 获取控件的文本模式
            pattern = control.GetTextPattern()
            if pattern:
                selection = pattern.GetSelection()
                if selection:
                    self.selected_text = selection[0].GetText(-1)
                    self.selection_time = time.perf_counter()
                    # 获取选中区域的文本内容（-1 表示获取完整文本）
                    return self.selected_text
        except Exception:
            # 忽略切换焦点或不受支持控件抛出的异常
            pass
        # print('error')
        return ""

    def get_clipboard_text(self, text):
        self.clipboard_text = text
        self.copy_time = time.perf_counter()

_instance = None

def init(*args, **kwargs) -> None:
    global _instance
    _instance = _textManager(*args, **kwargs)

def get() -> _textManager:
    """获取单例"""
    global _instance
    if _instance is None:
        raise RuntimeError("textManager 未初始化")
    return _instance
