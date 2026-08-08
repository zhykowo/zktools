from pages.base_page import BasePage
from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, QObject
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QWidget, QGridLayout
from PySide6.QtGui import QPalette, QColor, QFont
from widgets.svg_button import SvgButton
from widgets.core_button import CoreButton
from core.page_controller import page_signals
from resources.svgs import arrow_left_icon, arrow_right_icon
from resources.colors import get_accent_color
from utils.translator import Translator
from enum import Enum, auto
from functools import partial


class GridMode(Enum):
    NONE = auto()
    ORIGIN_LANG = auto()
    TARGET_LANG = auto()
    SERVER = auto()


class _Animator(QObject):
    """动画管理器，支持平滑高度动画与链式回调"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_group = None

    def animate_heights(self, animations_data: list[tuple[QWidget, int, int]], duration=300, easing=QEasingCurve.Type.OutQuart, on_finished=None):
        if self._active_group and self._active_group.state() == QParallelAnimationGroup.State.Running:
            self._active_group.stop()

        self._active_group = QParallelAnimationGroup(self)

        for widget, start_h, end_h in animations_data:
            widget.setFixedHeight(start_h)

            anim = QPropertyAnimation(widget, b"maximumHeight", self._active_group)
            anim.setDuration(duration)
            anim.setStartValue(start_h)
            anim.setEndValue(end_h)
            anim.setEasingCurve(easing)

            # 同步更新 minimumHeight
            anim.valueChanged.connect(widget.setMinimumHeight)

            # 动画结束后的边界对齐处理
            def create_finish_handler(w, target_end):
                def on_finish():
                    w.setMinimumHeight(target_end)
                    w.setMaximumHeight(target_end)
                return on_finish

            anim.finished.connect(create_finish_handler(widget, end_h))
            self._active_group.addAnimation(anim)

        if on_finished:
            self._active_group.finished.connect(on_finished)

        self._active_group.start()


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

    GRID_ITEM_HEIGHT = 36
    GRID_SPACING = 8
    RESULT_TEXT_HEIGHT = 120

    def __init__(self, parent=None):
        super().__init__(parent)

        self.translator = Translator()
        self.animator = _Animator(self)
        self.target_size = (400, 300)

        # 当前展开的网格类型状态
        self._current_grid_mode = GridMode.NONE

        layout = QVBoxLayout(self)

        # 1. 返回按钮
        self.back_btn = SvgButton(self, icon_size=24, svg_data=arrow_left_icon)
        self.back_btn.clicked.connect(self._on_back_clicked)

        # 透明调色板处理
        self.transparent_accent_color = QColor(get_accent_color())
        self.transparent_accent_color.setAlpha(10)

        # 2. 文本输入框与结果框
        self.input_text = QTextEdit(self)
        palette = self.input_text.palette()
        palette.setColor(QPalette.Active, QPalette.Base, self.transparent_accent_color)
        palette.setColor(QPalette.Inactive, QPalette.Base, QColor("#00000000"))
        palette.setColor(QPalette.Active, QPalette.Text, QColor("#ffffff"))
        self.input_text.setPalette(palette)

        self.result_text = QTextEdit(self)
        self.result_text.setPalette(palette)

        font = QFont()
        font.setPointSize(12)
        self.input_text.setFont(font)
        self.result_text.setFont(font)

        self.result_text.setMinimumHeight(0)
        self.result_text.setMaximumHeight(0)

        # 3. 通用平铺网格选择面板
        self.selection_grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.selection_grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(self.GRID_SPACING)

        self.selection_grid_widget.setMinimumHeight(0)
        self.selection_grid_widget.setMaximumHeight(0)

        # 4. 底部控制栏
        footer_layout = QHBoxLayout()
        btn_style_sheet = """
            QPushButton {border: none; color: white; background: transparent; padding: 0; font-size: 18px;}
            QPushButton:hover {color: grey; }
        """

        footer_layout.addStretch()

        self.origin_lang = QPushButton("English", self)
        self.origin_lang.setStyleSheet(btn_style_sheet)
        self.origin_lang.clicked.connect(lambda: self.display_lang_list("origin"))
        footer_layout.addWidget(self.origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon)
        self.swap_btn.clicked.connect(self._swap_languages)
        footer_layout.addWidget(self.swap_btn)

        self.target_lang = QPushButton("Chinese", self)
        self.target_lang.setStyleSheet(btn_style_sheet)
        self.target_lang.clicked.connect(lambda: self.display_lang_list("target"))
        footer_layout.addWidget(self.target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        footer_layout.addStretch()

        self.translation_server_btn = CoreButton("Google")
        self.translation_server_btn.clicked.connect(self._start_translation)
        self.translation_server_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.translation_server_btn.customContextMenuRequested.connect(self.display_server_list)
        footer_layout.addWidget(self.translation_server_btn)

        # 布局组织
        layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.input_text)
        layout.addWidget(self.result_text)
        layout.addWidget(self.selection_grid_widget)
        layout.addLayout(footer_layout)
        layout.addStretch()

    # ==================== 抽象核心逻辑 ====================
    def _request_grid_switch(self, mode: GridMode, items: list[str], current_value: str, on_select_callback):
        """网格切换控制中心：实现平滑过渡"""
        if self._current_grid_mode == mode:
            self._collapse_grid()
            return

        current_height = self.selection_grid_widget.height() if self._current_grid_mode != GridMode.NONE else 0
        self._current_grid_mode = mode

        # 填充新按钮并强制固定当前高度防止跳变
        self._populate_grid(items, current_value, on_select_callback)
        self.selection_grid_widget.setMaximumHeight(current_height)

        target_height = self._calculate_grid_height(len(items))

        # 准备动画
        animations = [(self.selection_grid_widget, current_height, target_height)]
        if self.result_text.height() > 0:
            animations.append((self.result_text, self.result_text.height(), 0))

        self.animator.animate_heights(animations)

    def _collapse_grid(self, on_finished=None):
        """收起当前网格动画"""
        self._current_grid_mode = GridMode.NONE
        current_height = self.selection_grid_widget.height()

        self.animator.animate_heights(
            animations_data=[(self.selection_grid_widget, current_height, 0)],
            on_finished=on_finished
        )

    def _populate_grid(self, items, current_value, on_select_callback):
        # 清空旧按钮
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 创建新按钮
        cols = 3
        for idx, text in enumerate(items):
            btn = CoreButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            if text != current_value:
                btn.setBgColor(self.transparent_accent_color)
            
            # 使用 functools.partial 代替 lambda 绑定，代码更清晰
            btn.clicked.connect(partial(self._handle_grid_item_click, text, on_select_callback))
            
            row, col = divmod(idx, cols)
            self.grid_layout.addWidget(btn, row, col)

    def _calculate_grid_height(self, item_count):
        cols = 3
        rows = (item_count + cols - 1) // cols
        return rows * self.GRID_ITEM_HEIGHT + (rows - 1) * self.GRID_SPACING

    def _handle_grid_item_click(self, selected_text: str, callback):
        """点击网格项后的逻辑处理"""
        callback(selected_text)
        self._collapse_grid()

    def display_lang_list(self, target_type="origin"):
        """显示语言选择网格"""
        mode = GridMode.ORIGIN_LANG if target_type == "origin" else GridMode.TARGET_LANG
        current_lang = self.origin_lang.text() if target_type == "origin" else self.target_lang.text()

        def set_language(selected_lang):
            if target_type == "origin":
                self.origin_lang.setText(selected_lang)
            else:
                self.target_lang.setText(selected_lang)

        self._request_grid_switch(mode, self.SUPPORTED_LANGUAGES, current_lang, set_language)

    def display_server_list(self):
        """显示翻译服务选择网格"""
        current_server = self.translation_server_btn.text()

        def set_server(selected_server):
            self.translation_server_btn.setText(selected_server)

        self._request_grid_switch(GridMode.SERVER, self.SUPPORTED_SERVERS, current_server, set_server)

    def _start_translation(self):
        """执行翻译并在网格收起后展开结果框"""
        text = self.input_text.toPlainText()
        server = self.translation_server_btn.text()
        from_lang = self.origin_lang.text()
        to_lang = self.target_lang.text()

        print(f"正在使用 [{server}] 将 '{text}' 从 {from_lang} 翻译为 {to_lang}...")

        result = self.translator.translate_text(text=text, server=server, from_lang=from_lang, to_lang=to_lang)
        self.result_text.setText(result)

        self._current_grid_mode = GridMode.NONE
        
        grid_start_h = self.selection_grid_widget.height()
        result_start_h = self.result_text.height()

        self.animator.animate_heights([
            (self.selection_grid_widget, grid_start_h, 0),
            (self.result_text, result_start_h, self.RESULT_TEXT_HEIGHT)
        ])

    def _swap_languages(self):
        """互换源语言与目标语言"""
        temp = self.origin_lang.text()
        self.origin_lang.setText(self.target_lang.text())
        self.target_lang.setText(temp)

    def _on_back_clicked(self):
        """返回逻辑：如果网格开启则收起，否则退出页面"""
        if self._current_grid_mode != GridMode.NONE:
            self._collapse_grid()
        else:
            page_signals.exit_self()