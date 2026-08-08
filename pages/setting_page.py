from pages.base_page import BasePage

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QLabel
from widgets.svg_button import SvgButton

from core.page_controller import page_signals

from resources.svgs import arrow_left_icon

class SettingPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = QVBoxLayout(self)
        back_btn = SvgButton(self, icon_size=24, svg_data=arrow_left_icon)
        back_btn.clicked.connect(lambda: page_signals.exit_self())

        title = QLabel("⚙️ 这是设置页面", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft) 
        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
