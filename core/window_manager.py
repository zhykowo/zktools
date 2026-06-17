from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation
from PySide6.QtWidgets import QApplication, QWidget

class WindowManager:
    """窗口悬浮岛管理器 - 负责窗口的显示/隐藏动画"""
    
    def __init__(self, window: QWidget):
        self.window = window
        
        # 状态标志
        self.is_expanded = False
        self.on_focus = False
        self.queue_state = False
        
        # 计算位置参数
        self.visible_height = 280
        screen = QApplication.primaryScreen().geometry()
        self.island_width = window.width()
        self.island_height = window.height()
        
        self.y_hidden = -self.island_height + self.visible_height
        self.y_shown = -30
        self.x_center = (screen.width() - self.island_width) // 2
        
        # 初始化位置（默认隐藏）
        window.move(self.x_center, self.y_hidden)
        
        # 创建动画
        self.anim = QPropertyAnimation(window, b"pos")
        self.anim.setDuration(800)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
    
    def animate(self, show: bool):
        """执行显示/隐藏动画"""
        if self.is_expanded == show:
            return
        if self.is_expanded and not show and (self.queue_state or self.on_focus):
            return
        
        self.is_expanded = show
        target_y = self.y_shown if show else self.y_hidden
        self.anim.stop()
        self.anim.setEndValue(QPoint(self.x_center, target_y))
        self.anim.start()
    
    def handle_focus_change(self, is_active: bool):
        """处理窗口焦点变化"""
        self.on_focus = is_active
        self.animate(is_active)