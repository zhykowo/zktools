from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QPushButton
from resources.colors import get_accent_color

class CoreButton(QPushButton):

  def __init__(self, text, parent=None):
    super().__init__(text, parent)

  def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

    accent_qcolor = get_accent_color()

    # 特殊处理退出按钮
    is_close_btn = self.objectName() == "CloseBtn"

    # 1. 状态判断 (Disabled -> Pressed -> Hover -> Normal)
    if not self.isEnabled():
      bg_color = QColor("#3a3a3a")  # 禁用状态：暗灰色
      text_color = QColor("#777777")
    elif self.isDown():  # 点击按下状态
      bg_color = (
          QColor("#962d22") if is_close_btn else accent_qcolor.darker(120)
      )
      text_color = QColor("white")
    elif self.underMouse():  # 悬停 Hover 状态
      bg_color = (
          QColor("#c0392b") if is_close_btn else accent_qcolor.lighter(110)
      )
      text_color = QColor("white")
    else:  # 正常状态
      bg_color = QColor("#e74c3c") if is_close_btn else accent_qcolor
      text_color = QColor("white")

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