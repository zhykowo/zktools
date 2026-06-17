from PySide6.QtWidgets import QWidget

class BasePage(QWidget):
    """所有页面的基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (100, 100)  # 默认大小，子类可以覆盖
    
    def on_show(self):
        """页面显示时调用，子类可以重写"""
        pass