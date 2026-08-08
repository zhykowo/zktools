
from PySide6.QtCore import QThread, QTimer, Qt, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel

from utils.clipboard_monitor import ClipboardMonitor


from core.page_controller import page_signals

from pages.base_page import BasePage

class ClipboardCtlPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.start_thread()
        self.target_size = (200, 50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("", self)
        # label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.label)

    def start_thread(self):

        # 3. 创建线程和工作者
        self.thread = QThread()
        self.worker = ClipboardMonitor()

        # 4. 将工作者移动到新线程
        self.worker.moveToThread(self.thread)

        # 5. 连接信号与槽
        # 线程启动时，执行工作者的耗时方法
        self.thread.started.connect(self.worker.start)
        
        # 接收工作者的进度信号，更新 UI
        self.worker.cbChanged.connect(self.update_ui)
        
        # 清理线程
        # self.worker.finished.connect(self.thread.quit)
        # self.worker.finished.connect(self.worker.deleteLater)
        # self.thread.finished.connect(self.thread.deleteLater)

        # 6. 启动线程
        self.thread.start()
    
    def quit_msg(self):
        page_signals.exit_self()

    @Slot()
    def update_ui(self):
        page_signals.immediate_switch("short_text")
        self.label.setText("Copied!")
        QTimer.singleShot(1500, self.quit_msg)