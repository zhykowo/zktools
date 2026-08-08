from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor, QPainter

# 自定义主容器 (替代 QSS 绘制背景和圆角)
class MainContainerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.default_background_color = QColor("#1d1d1f")
        self.background_color = self.default_background_color
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
        """使用 QPainter 纯原生高效绘制圆角矩形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background_color)

        # 绘制抗锯齿圆角背景
        rect = self.rect()
        painter.drawRoundedRect(rect, self.current_radius, self.current_radius)
