# core_button.py
from typing import cast

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton

from core.colors import (
    COLOR_DANGER,
    NEUTRAL_0,
    NEUTRAL_2,
    NEUTRAL_4,
    WHITE,
    color_manager,
    get_accent_color,
)


class CoreButton(QPushButton):
    def __init__(self, text, bg_color=None, text_color=None, radius=12, parent=None):
        super().__init__(text, parent)
        self._custom_bg_color = QColor(bg_color) if bg_color else None
        self._custom_text_color = QColor(text_color) if text_color else None
        # 由 setBgColor() 维护；先赋默认值，保证 paintEvent 之前一定可读
        self.bg_color = QColor()
        self.text_color = WHITE
        self.radius = radius

        self._on_accent_changed()

        color_manager.accent_color_changed.connect(self._on_accent_changed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

        # 1. 状态判断 (Disabled -> Pressed -> Hover -> Normal)
        if not self.isEnabled():
            bg_color = NEUTRAL_4
        elif self.isDown():  # 点击按下状态
            bg_color = self.bg_color.darker(120)
        elif self.underMouse():  # 悬停 Hover 状态
            bg_color = self.bg_color.lighter(110)
        else:  # 正常状态
            bg_color = self.bg_color

        text_color = self.text_color
        radius = self.radius

        # 2. 绘制背景（固定圆角，参考 text_editor 的圆角风格）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(self.rect(), radius, radius)

        # 3. 圆角边框：颜色取决于当前背景色（切换 bg_color 或 hover/按下后自动随之更新），
        #    圆角采用与 text_editor 相同的同心内缩画法，粗角处也能平滑贴合
        border_color = bg_color.lighter(120)
        half = 1.0
        border_rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
        border_radius = max(radius - half, 0.0)
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, border_radius, border_radius)

        # 4. 绘制文字
        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

    def setBgColor(self, bg_color: QColor | str = "accent"):
        """设置颜色，不指定bg_color时重置为系统配色"""

        if bg_color == "accent":
            self.bg_color = self.custom_accent_qcolor
        elif bg_color == "danger":
            self.bg_color = QColor(COLOR_DANGER)
        elif bg_color == "gray":
            self.bg_color = QColor(NEUTRAL_2)
        elif isinstance(bg_color, QColor):
            self.bg_color = bg_color
        else:
            raise TypeError(f"bg_color must be QColor, str, or None, got {type(bg_color)}")
        if self._custom_text_color:
            self.text_color = self._custom_text_color
        else:
            r, g, b, _ = cast("tuple[int, int, int, int]", self.bg_color.getRgbF())
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            self.text_color = NEUTRAL_0 if luminance > 0.5 else WHITE

        self.update()

    def _on_accent_changed(self, _new_color: QColor | None = None):
        """系统强调色变化时更新 accent 底色（仅当未自定义 bg_color 时）"""
        self.custom_accent_qcolor = get_accent_color()

        if self._custom_bg_color:
            self.setBgColor(self._custom_bg_color)
        else:
            self.setBgColor("gray")
