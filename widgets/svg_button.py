import sys
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QHBoxLayout, QWidget

from resources.colors import get_accent_color
class SvgButton(QPushButton):
    """
    通用的自定义矢量动画按钮
    支持传入 SVG 路径或 SVG 文本，自带悬停背景渐变、图标变色、图标旋转动画
    """
    def __init__(self, parent=None, size=36, icon_size=16, svg_data=None, hover_color=None, enable_rotation=False):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.icon_size = icon_size

        self.normal_color = QColor(255, 255, 255)
        if not hover_color:
            self.target_color = get_accent_color()
        else:
            self.target_color = QColor(hover_color)

        self.enable_rotation = enable_rotation

        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("border: none; background: transparent;")

        # 初始化 SVG 渲染器
        self.svg_renderer = QSvgRenderer()
        if svg_data:
            self.set_svg(svg_data)

        # 动画核心变量
        self._hover_progress = 0.0

        # 初始化属性动画
        self.animation = QPropertyAnimation(self, b"hoverProgress")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

    def set_svg(self, svg_data: str):
        """支持传入 SVG 文件路径 (.svg) 或者直接传入 SVG XML 字符串"""
        if svg_data.endswith('.svg'):
            self.svg_renderer.load(svg_data)
        else:
            # 如果是源码字符串，需要转换成 QByteArray
            self.svg_renderer.load(svg_data.encode('utf-8'))
        self.update()

    @Property(float)
    def hoverProgress(self):
        return self._hover_progress

    @hoverProgress.setter
    def hoverProgress(self, value):
        self._hover_progress = value
        self.update()

    def enterEvent(self, event):
        print("鼠标进入了某个组件")
        self.animation.setDirection(QPropertyAnimation.Forward)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        print("鼠标离开了某个组件")
        self.animation.setDirection(QPropertyAnimation.Backward)
        self.animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        p = self._hover_progress

        # 1. 绘制背景
        bg_alpha = int(p * 40)
        bg_color = QColor(self.target_color.red(), self.target_color.green(), self.target_color.blue(), bg_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(self.rect())

        if not self.svg_renderer.isValid():
            return

        # 2. 获取设备像素比
        dpr = self.devicePixelRatioF()
        # 计算物理像素尺寸（整数）
        pix_size = int(self.icon_size * dpr)
        # 创建高DPI Pixmap
        svg_pixmap = QPixmap(pix_size, pix_size)
        svg_pixmap.setDevicePixelRatio(dpr)
        svg_pixmap.fill(Qt.transparent)

        pix_painter = QPainter(svg_pixmap)
        # 渲染到逻辑尺寸（QPainter坐标自动根据dpr映射到物理像素）
        self.svg_renderer.render(pix_painter, QRectF(0, 0, self.icon_size, self.icon_size))
        pix_painter.end()

        # 3. 计算颜色
        r = int(self.normal_color.red() + (self.target_color.red() - self.normal_color.red()) * p)
        g = int(self.normal_color.green() + (self.target_color.green() - self.normal_color.green()) * p)
        b = int(self.normal_color.blue() + (self.target_color.blue() - self.normal_color.blue()) * p)
        icon_color = QColor(r, g, b)

        # 4. 染色（同样使用高DPI Pixmap）
        tinted_pixmap = QPixmap(pix_size, pix_size)
        tinted_pixmap.setDevicePixelRatio(dpr)
        tinted_pixmap.fill(Qt.transparent)

        tint_painter = QPainter(tinted_pixmap)
        tint_painter.drawPixmap(0, 0, svg_pixmap)
        tint_painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        tint_painter.fillRect(QRectF(0, 0, self.icon_size, self.icon_size), icon_color)
        tint_painter.end()

        # 5. 旋转并绘制（绘制时使用逻辑坐标，Qt自动处理缩放）
        angle = -p * 90.0
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2)
        if self.enable_rotation:
            painter.rotate(angle)
        # 绘制位置为逻辑尺寸的一半（因为pixmap逻辑尺寸就是icon_size）
        painter.drawPixmap(-self.icon_size / 2, -self.icon_size / 2, tinted_pixmap)
        painter.restore()