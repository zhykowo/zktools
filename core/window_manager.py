from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QSinglePointEvent
from PySide6.QtWidgets import QApplication, QWidget


class WindowDragFilter(QObject):
    """拖拽事件过滤器：可安装到任何 Widget 或 Button 上实现拖拽窗口"""

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self._drag_pos = QPoint()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            if (
                isinstance(event, QSinglePointEvent)
                and event.button() == Qt.MouseButton.LeftButton
            ):
                # 记录点击时鼠标相对窗口左上角的偏移量
                self._drag_pos = event.globalPosition().toPoint() - self.window.pos()
                return True
        elif (
            event.type() == QEvent.Type.MouseMove
            and isinstance(event, QSinglePointEvent)
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            # 随鼠标移动更新窗口位置
            self.window.move(event.globalPosition().toPoint() - self._drag_pos)
            return True
        return super().eventFilter(watched, event)


class WindowManager:
    """窗口悬浮岛管理器 - 负责窗口的显示/隐藏/拖拽/复位动画"""

    def __init__(self, window: QWidget):
        self.window = window

        # 状态标志
        self.is_expanded = False
        self.on_focus = False
        self.queue_state = False

        # 计算位置参数 (锚点位置)
        self.visible_height = 300
        screen = QApplication.primaryScreen().geometry()
        self.island_width = window.width()
        self.island_height = window.height()

        self.y_hidden = -self.island_height + self.visible_height
        self.y_shown = -30
        self.x_center = (screen.width() - self.island_width) // 2

        # 拖拽过滤器实例
        self.drag_filter = WindowDragFilter(window)

        # 初始化位置（默认隐藏）
        window.move(self.x_center, self.y_hidden)

        # 创建动画
        self.anim = QPropertyAnimation(window, b"pos")
        self.anim.setDuration(800)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def register_drag_handle(self, widget: QWidget):
        """便捷接口：注册任意组件/按钮为拖拽手柄"""
        widget.installEventFilter(self.drag_filter)

    def animate(self, show: bool, recenter: bool = False):
        """执行显示/隐藏或复位动画

        :param show: True 为显示，False 为隐藏
        :param recenter: True 时强制将 X 轴水平归位到中央锚点，False 时保持当前 X 轴位置
        """
        # 若非强制归位，且展开状态无变化，或触发了阻止隐藏的保护条件，则跳过
        if not recenter:
            if self.is_expanded == show:
                return
            if self.is_expanded and not show and (self.queue_state or self.on_focus):
                return

        self.is_expanded = show

        # 确定目标坐标
        target_x = self.x_center if recenter else self.window.x()
        target_y = self.y_shown if show else self.y_hidden

        self.anim.stop()
        self.anim.setEndValue(QPoint(target_x, target_y))
        self.anim.start()

    def handle_focus_change(self, is_active: bool):
        """处理窗口焦点变化"""
        self.on_focus = is_active
        self.animate(is_active)


class DragSignalBus(QObject):
    # 发送需要绑定拖拽的 QWidget 实例
    register_drag_handle_requested = Signal(object)


drag_bus = DragSignalBus()
