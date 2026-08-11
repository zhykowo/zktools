"""圆角文本编辑框：圆角背景 + 状态边框（accent/灰色）+ placeholder。"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QFrame, QTextEdit

from resources.colors import get_accent_color, get_purest_color


class RoundedTextEdit(QTextEdit):
    """带圆角背景与状态边框的 QTextEdit

    QTextEdit 的可视区域是 viewport，因此背景/边框/placeholder 全部绘制在
    viewport 上，且 Base 色必须保持透明，否则 super().paintEvent 会覆盖背景。

    - 边框：聚焦 -> accent 色高亮；悬停 -> 亮灰；常态 -> 暗灰；窗口失焦时整体压暗
    - 背景：圆角深色填充，聚焦时轻微提亮，与纯黑主界面形成层次
    - placeholder：文本为空且未聚焦时显示灰色提示文字
    """

    def __init__(self, placeholder: str = '', bg_color: str = '#26262b',
                 radius: int = 12, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._radius = radius
        self._bg_color = QColor(bg_color)

        self._accent = get_purest_color(get_accent_color())
        self._idle_border = QColor('#3a3a3d')
        self._hover_border = QColor('#5c5c62')
        self._placeholder_color = QColor('#6f6f76')

        # 去掉 QTextEdit 自带 frame / 边框，背景交由 paintEvent 统一绘制
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet('QTextEdit { background: transparent; border: none; }')

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        palette.setColor(QPalette.ColorRole.Text, QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.Highlight, self._accent)
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
        self.setPalette(palette)

        self.setViewportMargins(0, 0, 0, 0)
        # 文字内边距：让内容与圆角边缘保持呼吸感
        self.document().setDocumentMargin(10)
        # 文本变化时刷新 placeholder 的显示状态
        self.textChanged.connect(lambda: self.viewport().update())

    # ---------------- placeholder ----------------
    def set_placeholder(self, text: str):
        self._placeholder = text
        self.viewport().update()

    def get_placeholder(self) -> str:
        return self._placeholder

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

        if not self.window().isActiveWindow():
            border = border.darker(135)

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

            margin = self.document().documentMargin()
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
