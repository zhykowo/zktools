from pages.base_page import BasePage

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

class SettingPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = self.set_main_layout(d='v', title='Setting')

        title = QLabel("⚙️ 这是设置页面", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
