import sys
from PySide6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

class DynamicIslandMovementMixin:
    """
    灵动岛窗口移动核心逻辑组件
    可直接混入你的自定义窗口类中，或将其中的方法复制到你的窗口类
    """
    def init_island_movement(self, visible_height=10, animation_duration=300):
        """
        初始化灵动岛移动参数
        :param visible_height: 隐藏时留在屏幕顶部的像素高度（底边）
        :param animation_duration: 动画持续时间（毫秒）
        """
        # 1. 确保窗口无边框且置顶
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # 支持透明（可选）
        
        # 2. 启用鼠标追踪，确保能实时捕获 hover 事件
        self.setMouseTracking(True)
        
        # 3. 记录核心坐标参数
        self.visible_height = visible_height
        self.screen_geometry = QApplication.primaryScreen().geometry()
        self.island_width = self.width()
        self.island_height = self.height()
        
        # 计算隐藏和显示状态下的 Y 坐标
        self.y_hidden = -self.island_height + self.visible_height
        self.y_shown = 0  # 贴着屏幕顶端完全显示
        
        # 计算居中的 X 坐标
        self.x_center = (self.screen_geometry.width() - self.island_width) // 2
        
        # 4. 初始化窗口位置（默认隐藏，只留个底边）
        self.move(self.x_center, self.y_hidden)
        self.is_expanded = False
        
        # 5. 设置平滑动画
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(animation_duration)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic) # 渐出效果，更灵动

    def enterEvent(self, event):
        """重写鼠标划入事件：鼠标放上去，窗口往下移动显示出来"""
        self.animate_island(show=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """重写鼠标划出事件：鼠标移开，窗口往上缩回去"""
        # 注意：如果你的灵动岛有弹窗或子菜单，可能需要额外判断鼠标是否真的离开了整个组件区域
        self.animate_island(show=False)
        super().leaveEvent(event)

    def animate_island(self, show: bool):
        """执行上滑/下滑动画"""
        if self.is_expanded == show:
            return # 状态未改变，不重复触发动画
            
        self.is_expanded = show
        target_y = self.y_shown if show else self.y_hidden
        
        # 停止当前正在进行的动画，防止抽搐
        self.anim.stop()
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(QPoint(self.x_center, target_y))
        self.anim.start()

    @Slot(bool)
    @Slot()
    def toggle_island_via_signal(self, show: bool = True):
        """
        供外部代码信号（Emit）绑定的槽函数
        例如：接收到新通知时，外部 emit 一个信号触发此函数
        """
        self.animate_island(show)