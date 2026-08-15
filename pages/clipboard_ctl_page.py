
from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import QLabel

from core.page_router import page_router

import utils.clipboard_monitor as clipboard_monitor

from pages.base_page import BasePage

class ClipboardCtlPage(BasePage):
    PAGE_NAME = "clipboard"
    TITLE = "Clipboard"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (200, 50)

        layout = self.set_main_layout('h')

        self.label = QLabel("", self)
        # label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.label)

        clipboard_monitor.get().cbChanged.connect(self.update_ui)

        # 单一成员定时器：重复复制时重置计时而非堆积多个 singleShot
        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self.quit_msg)


    def quit_msg(self):
        page_router.exit_self(self.page_name)

    @Slot()
    def update_ui(self, _):
        if page_router.page_queue and page_router.page_queue[0] != 'home':
            return
        page_router.immediate_switch("clipboard")
        self.label.setText("Copied!")
        self._exit_timer.start(1500)