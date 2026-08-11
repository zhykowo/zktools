from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient

from resources.colors import (
    NEUTRAL_0, NEUTRAL_3, NEUTRAL_4,
)

# 自定义主容器 (替代 QSS 绘制背景和圆角)
class MainContainerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.default_background_color = NEUTRAL_0
        self.background_color = self.default_background_color
        # 外边框使用渐变描边：左上亮（白）→ 右下暗（灰），比单色更有层次
        self.border_color_start = NEUTRAL_3   # 渐变起点（左上，最亮）
        self.border_color_end = NEUTRAL_4       # 渐变终点（右下，偏灰）
        self.border_width = 1                         # 边框粗细
        self.current_radius = 25

    def set_background_color(self, color: QColor):
        """动态更新背景颜色并触发重绘"""
        self.background_color = color
        self.update()

    def set_radius(self, radius: int):
        """动态更新圆角半径并触发重绘"""
        self.current_radius = radius
        self.update()

    def paintEvent(self, event):
        """使用 QPainter 纯原生高效绘制圆角矩形 + 细边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

        # 绘制抗锯齿圆角背景（用完整矩形，保证填充不留毛边）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background_color)
        painter.drawRoundedRect(self.rect(), self.current_radius, self.current_radius)

        # 绘制外圈渐变边框。中心线矩形内缩 w/2、圆角半径取 R - w/2，
        # 使边框外边缘与背景圆角同心同半径，粗边框时角部也能平滑贴合
        half = self.border_width / 2.0
        border_rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
        border_radius = self.current_radius - half
        gradient = QLinearGradient(border_rect.topLeft(), border_rect.bottomRight())
        gradient.setColorAt(0.0, self.border_color_start)   # 左上：白
        gradient.setColorAt(1.0, self.border_color_end)     # 右下：灰
        painter.setPen(QPen(QBrush(gradient), self.border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, border_radius, border_radius)
