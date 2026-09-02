"""圆角文本编辑框：圆角背景 + 状态边框（accent/灰色）+ placeholder。"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QFrame, QTextEdit

from core.colors import (
    get_accent_color, get_purest_color,
    NEUTRAL_1, NEUTRAL_2, NEUTRAL_3,
    WHITE, NEUTRAL_4, COLOR_TRANSPARENT, color_manager,
)


class RoundedTextEdit(QTextEdit):
    """带圆角背景与状态边框的 QTextEdit

    QTextEdit 的可视区域是 viewport，因此背景/边框/placeholder 全部绘制在
    viewport 上，且 Base 色必须保持透明，否则 super().paintEvent 会覆盖背景。

    - 边框：聚焦 -> accent 色高亮；悬停 -> 亮灰；常态 -> 暗灰
    - 背景：圆角深色填充，聚焦时轻微提亮，与纯黑主界面形成层次
    - placeholder：文本为空且未聚焦时显示灰色提示文字
    """

    def __init__(self, placeholder: str = '', bg_color=NEUTRAL_1,
                 radius: int = 12, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._radius = radius
        self._bg_color = bg_color if isinstance(bg_color, QColor) else QColor(bg_color)

        self._accent = get_purest_color(get_accent_color())
        self._idle_border = NEUTRAL_2
        self._hover_border = NEUTRAL_3
        self._placeholder_color = NEUTRAL_4

        # 去掉 QTextEdit 自带 frame / 边框，背景交由 paintEvent 统一绘制
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptRichText(False)
        self.setStyleSheet('QTextEdit { background: transparent; border: none; }')

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, COLOR_TRANSPARENT)
        palette.setColor(QPalette.ColorRole.Text, WHITE)
        palette.setColor(QPalette.ColorRole.Highlight, self._accent)
        palette.setColor(QPalette.ColorRole.HighlightedText, WHITE)
        self.setPalette(palette)

        self.setViewportMargins(0, 0, 0, 0)
        # 文字内边距：让内容与圆角边缘保持呼吸感
        self.document().setDocumentMargin(10)
        # 文本变化时刷新 placeholder 的显示状态
        self.textChanged.connect(lambda: self.viewport().update())

        # 监听系统强调色变化，自动更新选区高亮与聚焦边框色
        color_manager.accent_color_changed.connect(self._on_accent_changed)

    # ---------------- placeholder ----------------
    def set_placeholder(self, text: str):
        self._placeholder = text
        self.viewport().update()

    def get_placeholder(self) -> str:
        return self._placeholder

    def _on_accent_changed(self, new_color: QColor):
        """系统强调色变化时更新选区高亮色与聚焦边框色"""
        self._accent = get_purest_color(new_color)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, self._accent)
        self.setPalette(palette)
        self.viewport().update()

    # ---------------- 绘制 ----------------
    def paintEvent(self, event):
        viewport = self.viewport()

        # 1. 圆角背景（聚焦时轻微提亮，形成层次）
        painter = QPainter(viewport)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(viewport.rect())

        bg = self._bg_color.lighter(103) if self.hasFocus() else self._bg_color
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, self._radius, self._radius)

        # 2. 状态边框：聚焦 -> accent；悬停 -> 亮灰；常态 -> 暗灰
        if self.hasFocus():
            border, width = self._accent, 2.0
        elif viewport.underMouse() and self.window().isActiveWindow():
            border, width = self._hover_border, 1.0
        else:
            border, width = self._idle_border, 1.0

        # 注意：不再按窗口激活状态压暗边框。本组件所在主窗口是 Qt.Tool 置顶悬浮窗，
        # 点击应用外部时 isActiveWindow() 会变为 False；此时暗灰边框若再 darker(135)
        # 会被压到与背景 NEUTRAL_1 几乎同色，看起来像边框"消失"。失焦时保持常态灰色。

        # 边框矩形内缩 width/2、圆角半径同步减 width/2，使边框外边缘与背景
        # 圆角同心同半径，粗边框时角部也能平滑贴合（与 main_container.py 修复一致）
        half = width / 2.0
        border_rect = rect.adjusted(half, half, -half, -half)
        border_radius = max(self._radius - half, 0.0)
        pen = QPen(border, width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, border_radius, border_radius)
        painter.end()

        # 3. 默认绘制：文本 + 光标 + 选区（Base 透明，不会覆盖背景）
        super().paintEvent(event)

        # 4. placeholder（文本为空且未聚焦时显示）
        if self._placeholder and not self.toPlainText() and not self.hasFocus():
            p = QPainter(viewport)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(self._placeholder_color)
            p.setFont(self.font())

            margin = int(self.document().documentMargin())
            fm = p.fontMetrics()
            text = fm.elidedText(
                self._placeholder, Qt.TextElideMode.ElideRight,
                viewport.width() - 2 * margin,
            )
            p.drawText(
                viewport.rect().adjusted(margin, margin, -margin, -margin),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                text,
            )
            p.end()
