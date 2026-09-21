# core_button.py
from typing import cast

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
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
    def __init__(self, text, bg_color=None, text_color=None, checked_color=None, radius=12, parent=None):
        super().__init__(text, parent)
        self._custom_bg_color = QColor(bg_color) if bg_color else None
        self._custom_text_color = QColor(text_color) if text_color else None
        self._custom_checked_color = QColor(checked_color) if checked_color else get_accent_color()

        # 由 setBgColor() 维护；先赋默认值，保证 paintEvent 之前一定可读
        self.bg_color = QColor()
        self.text_color = WHITE
        self.radius = radius

        # ---- 亮起复原动画配置 ----
        self._flash_factor = 0.0  # 亮光强度系数 (0.0 表示无亮光，1.0 表示最高亮)
        self._flash_anim = QPropertyAnimation(self, b"flash_factor")
        self._flash_anim.setEasingCurve(QEasingCurve.Type.OutCubic)  # OutCubic 实现快速亮起、缓慢平滑衰减

        self._on_accent_changed()

        color_manager.accent_color_changed.connect(self._on_accent_changed)
        self.toggled.connect(self._on_toggled)

        # 按下按钮时自动触发亮光动画
        self.pressed.connect(self.flash)

    # ---- Qt 属性定义（用于 QPropertyAnimation） ----
    def get_flash_factor(self) -> float:
        return self._flash_factor

    def set_flash_factor(self, val: float):
        self._flash_factor = val
        self.update()  # 触发重绘

    flash_factor = Property(float, get_flash_factor, set_flash_factor)

    def flash(self, duration: int = 600):
        """触发瞬间亮起并缓慢复原的动画（打断当前动画，重新开始）。

        :param duration: 动画复原持续时间 (毫秒)，默认 600ms
        """
        # 如果动画正在进行，先停止（实现可打断特性）
        if self._flash_anim.state() == QPropertyAnimation.State.Running:
            self._flash_anim.stop()

        self._flash_anim.setDuration(duration)
        self._flash_anim.setStartValue(1.0)  # 瞬间置为最亮
        self._flash_anim.setEndValue(0.0)  # 缓慢衰减至 0
        self._flash_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

        # 1. 状态判断 (Disabled -> Pressed -> Hover -> Normal)
        if not self.isEnabled():
            bg_color = NEUTRAL_4
        elif self._flash_factor > 0:
            # 闪光动画期间固定基色，避免按下/抬起切换导致二次闪动
            bg_color = self.bg_color
        elif self.isDown():  # 点击按下状态
            bg_color = self.bg_color.darker(120)
        elif self.underMouse():  # 悬停 Hover 状态
            bg_color = self.bg_color.lighter(110)
        else:  # 正常状态
            bg_color = self.bg_color

        # 1.5 动画叠加：若处于亮起衰减阶段，计算混色后的背景色
        if self._flash_factor > 0:
            # 计算高亮目标色（原色亮化并叠加白光，保证纯黑底色也能亮起）
            target_r = min(255, int(bg_color.red() * 1.5 + 50))
            target_g = min(255, int(bg_color.green() * 1.5 + 50))
            target_b = min(255, int(bg_color.blue() * 1.5 + 50))

            # 按照当前 flash_factor 进行颜色线性插值
            r = int(bg_color.red() + (target_r - bg_color.red()) * self._flash_factor)
            g = int(bg_color.green() + (target_g - bg_color.green()) * self._flash_factor)
            b = int(bg_color.blue() + (target_b - bg_color.blue()) * self._flash_factor)
            bg_color = QColor(r, g, b, bg_color.alpha())

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

        if self.isChecked() and self._custom_checked_color:
            self.setBgColor(self._custom_checked_color)
        elif self._custom_bg_color:
            self.setBgColor(self._custom_bg_color)
        else:
            self.setBgColor("gray")

    def _on_toggled(self, checked: bool):
        if checked and self._custom_checked_color:
            self.setBgColor(self._custom_checked_color)
        else:
            # 恢复默认背景（若有自定义 bg_color 则用自定义，否则用默认 "gray"）
            self.setBgColor(self._custom_bg_color if self._custom_bg_color else "gray")
