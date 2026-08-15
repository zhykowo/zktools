from pages.base_page import BasePage

from resources.svgs import settings_icon

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

class SettingPage(BasePage):
    PAGE_NAME = "setting"
    TITLE = "Setting"
    MODULE_CENTER_NAME = ""  # 设置页不显示在模块中心
    MODULE_CENTER_ICON = settings_icon

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = self.set_main_layout('v')

        title = QLabel("⚙️ 这是设置页面", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
