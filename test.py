from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMainWindow

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时焦点监听")

    def changeEvent(self, event):
        # 当窗口的激活状态发生改变时触发
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                print("【通知】窗口获得了焦点！")
            else:
                print("【通知】窗口失去了焦点！")
                
        # 记得调用父类的实现，确保其他事件正常处理
        # super().changeEvent(event)

app = QApplication([])
window = MyWindow()
window.show()
app.exec()