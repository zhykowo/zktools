import sys
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication


class ClipboardMonitor(QObject):
    # 正确的信号定义方式：必须是类属性
    cbChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clipboard = None

    def start(self):
        # 获取全局剪贴板对象
        self.clipboard = QApplication.clipboard()
        # 直接连接 Qt 内置的剪贴板改变信号
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        print("成功启动剪贴板监听...")

    @Slot()
    def on_clipboard_change(self):
        print("【提示】剪贴板内容已改变！")
        # 如果需要获取文本：
        text = self.clipboard.text()
        if text:
            print(f"内容为: {text}")

        # 触发自定义信号
        self.cbChanged.emit()


if __name__ == "__main__":
    # 使用 Qt 原生方法必须先实例化 QApplication
    app = QApplication(sys.argv)

    monitor = ClipboardMonitor()
    monitor.start()

    sys.exit(app.exec())