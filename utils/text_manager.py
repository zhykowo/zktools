import time
from typing import Any, cast

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
            pattern = cast("Any", control).GetTextPattern()
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

    def copy_selected_text(self, retries=5, delay=0.05):
        """复制当前选中文本（供一键翻译使用）

        优先通过 UI Automation 的文本模式直接读取选中内容（不污染剪贴板）；
        若目标控件不支持文本模式，则模拟 Ctrl+C 复制后再从剪贴板读取。
        """
        # 1. 优先直接读取选中文本，避免覆盖用户剪贴板
        text = self.get_selected_text()
        if text:
            return text

        # 2. 回退方案：模拟 Ctrl+C 后从剪贴板读取
        try:
            self.auto.SendKeys('{Ctrl}c')
        except Exception as e:
            print(f"[text_manager] 模拟 Ctrl+C 失败: {e}")
            return ""

        # 剪贴板内容更新是异步的，做几次短重试
        for _ in range(retries):
            clipboard_text = self.auto.GetClipboardText()
            if clipboard_text:
                self.selected_text = clipboard_text
                self.selection_time = time.perf_counter()
                return clipboard_text
            time.sleep(delay)

        print("[text_manager] 未获取到选中文本")
        return ""

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
