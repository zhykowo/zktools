from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from core.page_controller import page_signals

class BasePage(QWidget):
    """所有页面的基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (100, 100)  # 默认大小，子类可以覆盖

        # 创建页面级 Esc 快捷键
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(page_signals.exit_self)
    
    def on_show(self):
        """页面显示时调用，子类可以重写"""
        pass

    def clear_data(self):
        pass
        # print(f"🧹 已清空页面数据")
