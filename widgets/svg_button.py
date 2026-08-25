from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from widgets.hover import HoverShape, HoverWidget

from core.colors import get_accent_color, WHITE, color_manager

class SvgButton(HoverWidget):
    """继承 HoverWidget，天然具备圆形碰撞判定与物理 Hover 检测"""

    def __init__(self, parent=None, size=36, icon_size=16, svg_data=None, hover_color=None, enable_rotation=False):
        # 初始化基类，并指定为圆形碰撞区域 (HoverShape.CIRCLE)
        super().__init__(parent, shape=HoverShape.CIRCLE)

        self.setFixedSize(size, size)
        self.icon_size = icon_size
        self.normal_color = WHITE
        self._custom_hover_color = QColor(hover_color) if hover_color else None
        self.target_color = self._custom_hover_color or get_accent_color()
        self.enable_rotation = enable_rotation

        self.setCursor(Qt.PointingHandCursor)

        self.svg_renderer = QSvgRenderer()
        # 光栅化缓存：SVG 只渲染一次，之后 hover 动画每帧复用
        self._icon_cache = None        # 原始 SVG 渲染结果 (QPixmap)
        self._tint_pixmap = None       # 每帧复用的染色目标 (QPixmap)
        self._cached_dpr = 0.0
        self._cached_icon_size = 0

        if svg_data:
            self.set_svg(svg_data)

        # 动画定义
        self._hover_progress = 0.0
        self.animation = QPropertyAnimation(self, b"hoverProgress")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

        # 监听系统强调色变化，自动更新 hover 目标色
        color_manager.accent_color_changed.connect(self._on_accent_changed)

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
        self._icon_cache = None  # 使光栅化缓存失效，下次绘制时重建
        self.update()

    def _on_accent_changed(self, new_color: QColor):
        """系统强调色变化时更新 hover 目标色（仅当未自定义 hover_color 时）"""
        if self._custom_hover_color is None:
            self.target_color = QColor(new_color)
            self.update()

    # ---------- 光栅化缓存 ----------
    def _ensure_icon_cache(self):
        """惰性构建 SVG 光栅化缓存；仅当 SVG / icon_size / dpr 变化时重建"""
        dpr = self.devicePixelRatioF()
        if (self._icon_cache is not None
                and self._cached_dpr == dpr
                and self._cached_icon_size == self.icon_size):
            return

        self._icon_cache = None
        self._tint_pixmap = None
        if not self.svg_renderer.isValid():
            return

        pix_size = int(self.icon_size * dpr)
        icon = QPixmap(pix_size, pix_size)
        icon.setDevicePixelRatio(dpr)
        icon.fill(Qt.transparent)
        painter = QPainter(icon)
        self.svg_renderer.render(painter, QRectF(0, 0, self.icon_size, self.icon_size))
        painter.end()

        self._icon_cache = icon
        self._cached_dpr = dpr
        self._cached_icon_size = self.icon_size

    def _build_tinted_pixmap(self, p: float) -> QPixmap:
        """把缓存图标染成 (normal -> target) 的插值色；复用成员 pixmap，避免每帧分配"""
        cache = self._icon_cache
        if self._tint_pixmap is None or self._tint_pixmap.size() != cache.size():
            self._tint_pixmap = QPixmap(cache.size())
            self._tint_pixmap.setDevicePixelRatio(cache.devicePixelRatio())

        r = int(self.normal_color.red() + (self.target_color.red() - self.normal_color.red()) * p)
        g = int(self.normal_color.green() + (self.target_color.green() - self.normal_color.green()) * p)
        b = int(self.normal_color.blue() + (self.target_color.blue() - self.normal_color.blue()) * p)

        tinted = self._tint_pixmap
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, cache)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(QRectF(0, 0, self.icon_size, self.icon_size), QColor(r, g, b))
        painter.end()
        return tinted

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

        # 惰性构建/重建 SVG 光栅化缓存（仅首次 / icon_size / dpr 变化时执行）
        self._ensure_icon_cache()
        if self._icon_cache is None:
            return

        # 每帧仅做一次廉价的位图染色（复用成员 pixmap，无分配、无 SVG 重渲染）
        tinted = self._build_tinted_pixmap(p)

        # 绘制
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2)
        if self.enable_rotation:
            painter.rotate(-p * 90.0)
        painter.drawPixmap(-self.icon_size / 2, -self.icon_size / 2, tinted)
        painter.restore()
