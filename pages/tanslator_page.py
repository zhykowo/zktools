from pages.base_page import BasePage

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
from PySide6.QtGui import QPalette, QColor, QFont

from widgets.SvgButton import SvgButton
from widgets.CoreButton import CoreButton

from core.page_controller import page_signals

from resources.svgs import arrow_left_icon, arrow_right_icon
from resources.colors import get_accent_color

class TranslatorPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (400, 300)

        layout = QVBoxLayout(self)
        back_btn = SvgButton(self, icon_size=24, svg_data=arrow_left_icon)
        back_btn.clicked.connect(lambda: page_signals.exit_self())

        # title = QLabel("这是翻译页面", self)
        # title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        accent_color = get_accent_color()
        accent_color.setAlpha(10)

        input_text = QTextEdit(self)
        palette = input_text.palette()
        palette.setColor(QPalette.Active, QPalette.Base, accent_color)
        palette.setColor(QPalette.Inactive, QPalette.Base, QColor("#00000000"))
        palette.setColor(QPalette.Active, QPalette.Text, QColor("#ffffff"))
        input_text.setPalette(palette)

        font = QFont()
        font.setPointSize(14)
        input_text.setFont(font)

        footer_layout = QHBoxLayout()

        origin_lang = QLabel("English", self)
        footer_layout.addWidget(origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon, hover_color="#0980ff")
        footer_layout.addWidget(swap_btn)

        target_lang = QLabel("Chinese", self)
        footer_layout.addWidget(target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        change_service_btn = CoreButton("Google Translator")
        footer_layout.addWidget(change_service_btn)

        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft) 
        layout.addWidget(input_text)
        layout.addLayout(footer_layout)
        layout.addStretch()
