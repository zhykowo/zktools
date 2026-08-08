import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("鼠标追踪示例")
        
        self.btn1 = QPushButton("按钮1")
        self.btn1.setObjectName("button1")
        self.btn2 = QPushButton("按钮2")
        self.btn2.setObjectName("button2")
        self.label = QLabel("标签")
        self.label.setObjectName("myLabel")
        
        layout = QVBoxLayout()
        layout.addWidget(self.btn1)
        layout.addWidget(self.btn2)
        layout.addWidget(self.label)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # 使用定时器每500ms检测一次鼠标位置下的控件
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_mouse_position)
        self.timer.start(500)
    
    def check_mouse_position(self):
        cursor_pos = self.cursor().pos()  # 获取鼠标全局坐标
        widget = QApplication.widgetAt(cursor_pos)  # 获取该坐标下的控件
        if widget:
            print(f"鼠标下控件: {widget.objectName()} ({widget.metaObject().className()})")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())