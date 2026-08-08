
from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import QLabel

from core.page_controller import page_signals

import utils.clipboard_monitor as clipboard_monitor

from pages.base_page import BasePage

class ClipboardCtlPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (200, 50)

        layout = self.set_main_layout('h')

        self.label = QLabel("", self)
        # label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.label)

        clipboard_monitor.get().cbChanged.connect(self.update_ui)

    
    def quit_msg(self):
        page_signals.exit_self()

    @Slot()
    def update_ui(self, text):
        page_signals.immediate_switch("short_text")
        self.label.setText("Copied!")
        QTimer.singleShot(1500, self.quit_msg)