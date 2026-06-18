import sys
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget


class AnimatedCloseButton(QPushButton):

    def __init__(self, parent=None, size=36, icon_size=16, line_width=2.0):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.icon_size = icon_size
        self.line_width = line_width  # 矢量线条宽度

        # 设置鼠标悬停手势
        self.setCursor(Qt.PointingHandCursor)

        # 隐藏默认边框和背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("border: none; background: transparent;")

        # 动画核心变量：hover进度 (0.0 -> 1.0)
        self._hover_progress = 0.0

        # 初始化属性动画，明确起止值以解决警告
        self.animation = QPropertyAnimation(self, b"hoverProgress")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

    @Property(float)
    def hoverProgress(self):
        return self._hover_progress

    @hoverProgress.setter
    def hoverProgress(self, value):
        self._hover_progress = value
        self.update()  # 触发重绘

    def enterEvent(self, event):
        self.animation.setDirection(QPropertyAnimation.Forward)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.setDirection(QPropertyAnimation.Backward)
        self.animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # ====== 核心优化点：开启最高级别抗锯齿 ======
        painter.setRenderHint(QPainter.Antialiasing, True)
        # 高级抗锯齿，对文本和复杂路径效果显著
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        # 不要开启 SmoothPixmapTransform，因为我们不再绘制 Pixmap

        p = self._hover_progress

        # 1. 计算并绘制圆形背景 (不变)
        bg_alpha = int(p * 40)
        bg_color = QColor(232, 17, 35, bg_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(self.rect())

        # 2. 计算图标线条颜色 (纯白 -> 红色) (不变)
        r = int(255 + (232 - 255) * p)
        g = int(255 + (17 - 255) * p)
        b = int(255 + (35 - 255) * p)
        icon_color = QColor(r, g, b)

        # 3. 计算旋转角度并定位 (不变)
        angle = p * 90.0
        
        painter.save()
        # 移至中心，开启旋转
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(angle)

        # ====== 核心优化点：改用矢量绘制图标 ======
        
        # A. 设置画笔：抗锯齿、精确线宽、圆角笔触（可以让线条末端更圆润好看）
        pen = QPen(icon_color, self.line_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        # B. 精确计算“X”的四个顶点
        # 图标中心在 (0,0)，我们需要根据 icon_size 计算相对坐标
        # 偏移量 half_s 确保我们在一个精准的像素点开始绘制
        half_s = (self.icon_size / 2) - 0.5 

        # C. 使用 QPainterPath 绘制两条线构成 X
        # 线条1：左上到右下
        painter.drawLine(QPointF(-half_s, -half_s), QPointF(half_s, half_s))
        # 线条2：左下到右上
        painter.drawLine(QPointF(-half_s, half_s), QPointF(half_s, -half_s))

        painter.restore()


# --- 测试窗口 ---
class DemoWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom Close Button Demo")
        self.resize(300, 200)

        # 设置深色背景，以便看清初始的白色图标
        self.setStyleSheet("background-color: #1E1E1E;")

        # 居中放置按钮
        center_widget = QWidget()
        layout = QVBoxLayout(center_widget)
        layout.setAlignment(Qt.AlignCenter)

        # 实例自定义按钮 (大小 40x40，内部图标矢量绘制，设置合适的线宽)
        # 调整 line_width 为 2.0，能让小图标更饱满清晰
        self.close_btn = AnimatedCloseButton(self, size=40, icon_size=16, line_width=2.0)
        self.close_btn.clicked.connect(self.close)

        layout.addWidget(self.close_btn)
        self.setCentralWidget(center_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 对于小图标，有时设置高质量像素图混合模式反而不如直接矢量绘制清晰
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())