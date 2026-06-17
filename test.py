import sys
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtCore import Qt, QRectF

class CustomRoundButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        # 1. 设置按钮的推荐大小（避免纯绘图时组件坍塌）
        self.setMinimumSize(140, 45)
        
        # 2. 定义不同状态下的颜色
        self._normal_bg = QColor("#3498db")   # 默认：蓝色
        self._hover_bg = QColor("#2980b9")    # 悬停：深蓝
        self._pressed_bg = QColor("#1c5980")  # 按下：暗蓝
        self._text_color = QColor("#ffffff")  # 文字：白色
        
        # 3. 设置圆角半径
        self._radius = 15.0

    # 重写鼠标进入事件，触发重绘实现 Hover 效果
    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()  # 强制刷新界面，触发 paintEvent

    # 重写鼠标离开事件，恢复原状
    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()  # 强制刷新界面，触发 paintEvent

    # 核心绘制逻辑
    def paintEvent(self, event):
        # 初始化画布
        painter = QPainter(self)
        
        # 开启【极其重要】的抗锯齿，否则圆角会有难看的锯齿
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 1. 根据当前按钮状态动态切换背景色
        if self.isDown():
            bg_color = self._pressed_bg
        elif self.underMouse():
            bg_color = self._hover_bg
        else:
            bg_color = self._normal_bg

        # 2. 精确计算绘制区域
        # 将原始矩形整体向内缩 0.5 像素，防止抗锯齿引发的边缘被控件边界裁剪的问题
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        
        # 3. 开始绘制背景
        painter.setPen(Qt.NoPen)             # 禁用边框线
        painter.setBrush(QBrush(bg_color))    # 设置填充色
        painter.drawRoundedRect(rect, self._radius, self._radius) # 绘制圆角矩形

        # 4. 开始绘制文本
        painter.setPen(QPen(self._text_color)) # 设置文字颜色
        painter.setFont(self.font())           # 使用按钮自带的字体设置
        
        # 在矩形正中央绘制传入的文字
        painter.drawText(rect, Qt.AlignCenter, self.text())

        # 结束绘制（释放资源）
        painter.end()


# ==================== 测试窗口 ====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 paintEvent 圆角按钮")
        self.resize(350, 250)
        
        # 给窗口加个浅色背景，更能看清按钮的圆角抗锯齿效果
        self.setStyleSheet("background-color: #f8f9fa;")

        # 布局管理器
        layout = QVBoxLayout(self)
        
        # 创建自定义按钮
        self.btn1 = CustomRoundButton("标准圆角按钮")
        
        self.btn2 = CustomRoundButton("大圆角(胶囊状)")
        self.btn2._radius = 22.0 # 动态修改圆角半径（高度45的一半，呈现完美胶囊状）
        self.btn2._normal_bg = QColor("#2ecc71") # 顺便改个绿色主题
        self.btn2._hover_bg = QColor("#27ae60")
        self.btn2._pressed_bg = QColor("#1e7e43")

        # 将按钮添加到布局中，并居中显示
        layout.addWidget(self.btn1, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn2, alignment=Qt.AlignCenter)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())