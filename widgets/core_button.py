from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QPushButton
from resources.colors import get_accent_color, get_purest_color

class CoreButton(QPushButton):

  def __init__(self, text, bg_color=None, text_color=None, parent=None):
    super().__init__(text, parent)

    self.accent_qcolor = get_accent_color()
    self.accent_qcolor = get_purest_color(self.accent_qcolor)

    self.bg_color = QColor(bg_color) if bg_color else self.accent_qcolor
    self.text_color = QColor(text_color) if text_color else QColor("white")

  def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

    # 1. 状态判断 (Disabled -> Pressed -> Hover -> Normal)
    if not self.isEnabled():
      bg_color = QColor("gray")
    elif self.isDown():  # 点击按下状态
      bg_color = self.bg_color.darker(120)
    elif self.underMouse():  # 悬停 Hover 状态
      bg_color = self.bg_color.lighter(110)
    else:  # 正常状态
      bg_color = self.bg_color

    text_color = self.text_color

    # 2. 动态计算胶囊圆角
    radius = self.height() // 2 - 1

    # 3. 绘制背景
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(bg_color))
    painter.drawRoundedRect(self.rect(), radius, radius)

    # 4. 绘制文字
    painter.setPen(text_color)
    painter.setFont(self.font())
    painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

  def setBgColor(self, bg_color: QColor):
    self.bg_color = bg_color

  def resetBgColor(self):
    self.bg_color = self.accent_qcolor