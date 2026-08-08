from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from widgets.hover import HoverShape, HoverWidget

try:
    from resources.colors import get_accent_color
except ImportError:
    def get_accent_color():
        return QColor(0, 120, 215)

class SvgButton(HoverWidget):
    """继承 HoverWidget，天然具备圆形碰撞判定与物理 Hover 检测"""

    def __init__(self, parent=None, size=36, icon_size=16, svg_data=None, hover_color=None, enable_rotation=False):
        # 初始化基类，并指定为圆形碰撞区域 (HoverShape.CIRCLE)
        super().__init__(parent, shape=HoverShape.CIRCLE)
        
        self.setFixedSize(size, size)
        self.icon_size = icon_size
        self.normal_color = QColor(255, 255, 255)
        self.target_color = QColor(hover_color) if hover_color else get_accent_color()
        self.enable_rotation = enable_rotation

        self.setCursor(Qt.PointingHandCursor)

        self.svg_renderer = QSvgRenderer()
        if svg_data:
            self.set_svg(svg_data)

        # 动画定义
        self._hover_progress = 0.0
        self.animation = QPropertyAnimation(self, b"hoverProgress")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

    # 重写基类的 进入/离开 钩子函数
    def on_hover_enter(self):
        self.animation.setDirection(QPropertyAnimation.Forward)
        if self.animation.state() == QPropertyAnimation.Stopped:
            self.animation.start()

    def on_hover_leave(self):
        self.animation.setDirection(QPropertyAnimation.Backward)
        if self.animation.state() == QPropertyAnimation.Stopped:
            self.animation.start()

    # 属性与绘图保持不变
    @Property(float)
    def hoverProgress(self):
        return self._hover_progress

    @hoverProgress.setter
    def hoverProgress(self, value):
        self._hover_progress = value
        self.update()

    def set_svg(self, svg_data: str):
        if svg_data.endswith('.svg'):
            self.svg_renderer.load(svg_data)
        else:
            self.svg_renderer.load(svg_data.encode('utf-8'))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        p = self._hover_progress

        # 绘制背景
        bg_alpha = int(p * 40)
        bg_color = QColor(self.target_color.red(), self.target_color.green(), self.target_color.blue(), bg_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(self.rect())

        if not self.svg_renderer.isValid():
            return

        # 图标绘制
        dpr = self.devicePixelRatioF()
        pix_size = int(self.icon_size * dpr)
        svg_pixmap = QPixmap(pix_size, pix_size)
        svg_pixmap.setDevicePixelRatio(dpr)
        svg_pixmap.fill(Qt.transparent)

        pix_painter = QPainter(svg_pixmap)
        self.svg_renderer.render(pix_painter, QRectF(0, 0, self.icon_size, self.icon_size))
        pix_painter.end()

        # 颜色计算与染色
        r = int(self.normal_color.red() + (self.target_color.red() - self.normal_color.red()) * p)
        g = int(self.normal_color.green() + (self.target_color.green() - self.normal_color.green()) * p)
        b = int(self.normal_color.blue() + (self.target_color.blue() - self.normal_color.blue()) * p)
        
        tinted_pixmap = QPixmap(pix_size, pix_size)
        tinted_pixmap.setDevicePixelRatio(dpr)
        tinted_pixmap.fill(Qt.transparent)

        tint_painter = QPainter(tinted_pixmap)
        tint_painter.drawPixmap(0, 0, svg_pixmap)
        tint_painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        tint_painter.fillRect(QRectF(0, 0, self.icon_size, self.icon_size), QColor(r, g, b))
        tint_painter.end()

        # 绘制
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2)
        if self.enable_rotation:
            painter.rotate(-p * 90.0)
        painter.drawPixmap(-self.icon_size / 2, -self.icon_size / 2, tinted_pixmap)
        painter.restore()