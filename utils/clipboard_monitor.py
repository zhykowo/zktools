from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

class _ClipboardMonitor(QObject):
    cbChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self._on_change)

    @Slot()
    def _on_change(self):
        text = self.clipboard.text()
        if text:
            self.cbChanged.emit(text)

_instance = None
def init(*args, **kwargs) -> None:
    global _instance
    _instance = _ClipboardMonitor(*args, **kwargs)

def get() -> _ClipboardMonitor:
    """获取剪贴板监听器单例"""
    global _instance
    if _instance is None:
        raise RuntimeError("ClipboardMonitor 未初始化")
    return _instance