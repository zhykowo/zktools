from pages.base_page import BasePage

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QWidget, QGridLayout
)
from PySide6.QtGui import QPalette, QColor, QFont

from widgets.SvgButton import SvgButton
from widgets.CoreButton import CoreButton

from core.page_controller import page_signals

from resources.svgs import arrow_left_icon, arrow_right_icon
from resources.colors import get_accent_color

from utils.translator import Translator

class TranslatorPage(BasePage):
    SUPPORTED_LANGUAGES = [
        "Auto", "English", "Chinese",
        "Japanese", "Korean", "French",
        "German", "Spanish", "Russian"
    ]
    SUPPORTED_SERVERS = [
        "Google", "DeepL", "Baidu", 
        "Bing", "OpenAI", "Youdao"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.translator = Translator()

        self.target_size = (400, 300)

        layout = QVBoxLayout(self)

        # 1. 返回按钮
        self.back_btn = SvgButton(self, icon_size=24, svg_data=arrow_left_icon)
        self.back_btn.clicked.connect(self._on_back_clicked)

        # 透明调色板处理 (使用 QColor 副本避免修改原全局颜色)
        transparent_accent_color = QColor(get_accent_color())
        transparent_accent_color.setAlpha(10)

        # 2. 文本输入框
        self.input_text = QTextEdit(self)
        palette = self.input_text.palette()
        palette.setColor(QPalette.Active, QPalette.Base, transparent_accent_color)
        palette.setColor(QPalette.Inactive, QPalette.Base, QColor("#00000000"))
        palette.setColor(QPalette.Active, QPalette.Text, QColor("#ffffff"))
        self.input_text.setPalette(palette)

        self.result_text = QTextEdit(self)
        self.result_text.setPalette(palette)

        font = QFont()
        font.setPointSize(12)
        self.input_text.setFont(font)
        self.result_text.setFont(font)
        self.result_text.hide()

        # 3. 通用平铺网格选择面板
        self.selection_grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.selection_grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(8)
        self.selection_grid_widget.hide()

        # 4. 底部控制栏
        footer_layout = QHBoxLayout()
        btn_style_sheet = """
            QPushButton {border: none; color: white; background: transparent; padding: 0; font-size: 18px;}
            QPushButton:hover {color: grey; }
        """

        footer_layout.addStretch()

        # 源语言按钮
        self.origin_lang = QPushButton("English", self)
        self.origin_lang.setStyleSheet(btn_style_sheet)
        self.origin_lang.clicked.connect(lambda: self.display_lang_list("origin"))
        footer_layout.addWidget(self.origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        # 语言互换按钮
        self.swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon)
        self.swap_btn.clicked.connect(self._swap_languages)
        footer_layout.addWidget(self.swap_btn)

        # 目标语言按钮
        self.target_lang = QPushButton("Chinese", self)
        self.target_lang.setStyleSheet(btn_style_sheet)
        self.target_lang.clicked.connect(lambda: self.display_lang_list("target"))
        footer_layout.addWidget(self.target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        footer_layout.addStretch()

        # 翻译服务按钮
        self.translation_server_btn = CoreButton("Google")
        self.translation_server_btn.clicked.connect(self._start_translation)
        self.translation_server_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.translation_server_btn.customContextMenuRequested.connect(lambda pos: self.display_server_list())
        footer_layout.addWidget(self.translation_server_btn)

        # 布局组织
        layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.input_text)
        layout.addWidget(self.result_text)
        layout.addWidget(self.selection_grid_widget)
        layout.addLayout(footer_layout)
        layout.addStretch()

    # ==================== 抽象核心函数 ====================
    def _show_grid_selection(self, items: list[str], current_value: str, on_select_callback):
        """通用网格选择显示抽象函数"""
        # 清空原有网格中的按钮
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 动态生成按钮并装载进网格
        cols = 3

        for idx, text in enumerate(items):
            btn = CoreButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            if not text == current_value:
                btn.setBgColor(QColor('grey'))
            btn.clicked.connect(lambda _, t=text: self._handle_grid_item_click(t, on_select_callback))

            row, col = divmod(idx, cols)
            self.grid_layout.addWidget(btn, row, col)

        # self.input_text.hide()
        self.selection_grid_widget.show()

    def _handle_grid_item_click(self, selected_text: str, callback):
        """网格项点击中转处理"""
        callback(selected_text)
        self._restore_input_view()

    def display_lang_list(self, target_type="origin"):
        """显示语言选择网格"""
        current_lang = self.origin_lang.text() if target_type == "origin" else self.target_lang.text()

        def set_language(selected_lang):
            if target_type == "origin":
                self.origin_lang.setText(selected_lang)
            else:
                self.target_lang.setText(selected_lang)

        self._show_grid_selection(self.SUPPORTED_LANGUAGES, current_lang, set_language)

    def display_server_list(self):
        """右键点击：显示翻译服务选择网格"""
        current_server = self.translation_server_btn.text()

        def set_server(selected_server):
            self.translation_server_btn.setText(selected_server)

        self._show_grid_selection(self.SUPPORTED_SERVERS, current_server, set_server)

    def _start_translation(self):
        """左键点击：执行翻译逻辑"""
        text = self.input_text.toPlainText()
        server = self.translation_server_btn.text()
        from_lang = self.origin_lang.text()
        to_lang = self.target_lang.text()

        print(f"正在使用 [{server}] 将 '{text}' 从 {from_lang} 翻译为 {to_lang}...")

        result = self.translator.translate_text(text=text, server=server, from_lang=from_lang, to_lang=to_lang)
        self.result_text.setText(result)
        self.result_text.show()

    def _swap_languages(self):
        """补全：互换源语言与目标语言"""
        temp = self.origin_lang.text()
        self.origin_lang.setText(self.target_lang.text())
        self.target_lang.setText(temp)

    def _restore_input_view(self):
        """恢复文本输入框视图"""
        self.selection_grid_widget.hide()
        # self.input_text.show()

    def _on_back_clicked(self):
        """返回逻辑：如果在网格选择界面，先切回输入框"""
        if self.selection_grid_widget.isVisible():
            self._restore_input_view()
        else:
            page_signals.exit_self()

class _Animator:
    pass