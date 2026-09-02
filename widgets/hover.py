from enum import Enum
from PySide6.QtCore import QPointF, Signal, QEvent, Qt, QRectF
from PySide6.QtGui import QPainterPath, QMouseEvent, QSinglePointEvent
from typing import cast
from PySide6.QtWidgets import QWidget


class HoverShape(Enum):
    RECTANGLE = 0  # 矩形
    CIRCLE = 1  # 内切圆/正圆
    ROUNDED_RECT = 2  # 圆角矩形
    CUSTOM = 3  # 自定义路径


class HoverWidget(QWidget):
    """
    通用精准悬停组件基类
    完全绕过原生的 enterEvent/leaveEvent，采用纯数学几何距离判定。
    """

    # 信号定义
    hover_entered = Signal()  # 鼠标真正进入几何区域
    hover_left = Signal()  # 鼠标真正离开几何区域
    clicked = Signal(bool)  # 在几何区域内完成有效点击

    def __init__(
        self,
        parent=None,
        shape: HoverShape = HoverShape.RECTANGLE,
        border_radius: float = 0.0,
    ):
        super().__init__(parent)
        self._shape = shape
        self._border_radius = border_radius

        self._is_hovered = False
        self._is_pressed = False

        # 强制开启悬停属性与追踪
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    # ---------------- 核心碰撞几何判定 ----------------
    def set_hover_shape(self, shape: HoverShape, border_radius: float = 0.0):
        """动态设置检测形状"""
        self._shape = shape
        self._border_radius = border_radius
        self.update()

    def get_custom_path(self) -> QPainterPath:
        """如果 shape 选择 HoverShape.CUSTOM，子类可重写此函数返回任意矢量形状"""
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def contains_point(self, pos) -> bool:
        """根据当前设定的几何形状，精准检测点 pos 是否在内部"""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        if self._shape == HoverShape.RECTANGLE:
            return self.rect().contains(int(x), int(y))

        elif self._shape == HoverShape.CIRCLE:
            cx, cy = w / 2.0, h / 2.0
            dx, dy = x - cx, y - cy
            radius = min(w, h) / 2.0
            return (dx * dx + dy * dy) <= (radius * radius)

        elif self._shape == HoverShape.ROUNDED_RECT:
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(self.rect()), self._border_radius, self._border_radius
            )
            return path.contains(pos)

        elif self._shape == HoverShape.CUSTOM:
            return self.get_custom_path().contains(pos)

        return False

    # ---------------- 事件拦截与驱动 ----------------
    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.HoverMove, QEvent.Type.MouseMove):
            if isinstance(event, QSinglePointEvent):
                pos = event.position()
            else:
                return super().event(event)
            self._update_hover_state(self.contains_point(pos))

        elif event.type() in (QEvent.Type.HoverLeave, QEvent.Type.Leave):
            self._update_hover_state(False)

        return super().event(event)

    def _update_hover_state(self, is_hovered: bool):
        if self._is_hovered == is_hovered:
            return

        self._is_hovered = is_hovered
        if is_hovered:
            self.on_hover_enter()
            self.hover_entered.emit()
        else:
            self.on_hover_leave()
            self.hover_left.emit()

    # 虚函数：供子类覆盖（也可以直接连接 hover_entered / hover_left 信号）
    def on_hover_enter(self):
        pass

    def on_hover_leave(self):
        pass

    # ---------------- 统一点击模拟 ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if isinstance(event, QSinglePointEvent):
                pos = event.position()
            else:
                pos = QPointF()
            if self.contains_point(pos):
                self._is_pressed = True
        super().mousePressEvent(cast(QMouseEvent, event))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            if isinstance(event, QSinglePointEvent):
                pos = event.position()
            else:
                pos = QPointF()
            if self.contains_point(pos):
                self.clicked.emit(False)
        super().mouseReleaseEvent(cast(QMouseEvent, event))
