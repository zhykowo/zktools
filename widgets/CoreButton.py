from PySide6.QtGui import QPainter, QColor, QBrush, QPen, Qt
from PySide6.QtWidgets import QPushButton

class CoreButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

    def paintEvent(self, event):
        # 抛弃默认绘制，自己用 QPainter 描绘一切
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

        # 1. 根据状态决定颜色
        if not self.isEnabled():
            bg_color = QColor("#2c3e50")
        elif self.underMouse():  # Hover 状态
            bg_color = QColor("#415b76")
        else:                   # 正常状态
            bg_color = QColor("#34495e")

        # 特殊处理退出按钮颜色
        if self.objectName() == "CloseBtn":
            bg_color = QColor("#c0392b") if self.underMouse() else QColor("#e74c3c")

        # 2. 核心：动态计算当前按钮高度允许的最大圆角 (绝对不坍塌)
        radius = self.height() // 2 - 1

        # 3. 绘制背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(self.rect(), radius, radius)

        # 4. 绘制文字
        painter.setPen(QPen(QColor("white")))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())