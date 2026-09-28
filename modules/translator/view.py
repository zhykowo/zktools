"""翻译模块 —— 界面层（view）

只负责两件事：把用户操作翻译成信号发出去，把 controller 送来的状态渲染出来。

硬约束（这是本文件能脱离逻辑层独立单测的前提）：

- 不 import Translator / TranslatorScript / 任何业务模块，不知道翻译怎么发生；
- 不读业务配置（CONFIG 的语种、服务名等一律由 controller 推送进来）；
- 网格（SelectionGrid）的展开/收起、结果区高度动画等纯视觉行为就地消化；
- 对外只有「信号出 + 槽入」两种接口，不持有任何业务状态。

因此本文件可以在完全不构造 TranslatorScript 的情况下单测：
喂信号 → 断言控件；调槽 → 断言渲染与发出的信号。
"""

from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QHBoxLayout

from pages.base_page import BasePage
from resources.svgs import arrow_right_icon, translate_icon
from widgets.core_button import CoreButton
from widgets.selection_grid import SelectionGrid
from widgets.svg_button import SvgButton
from widgets.text_editor import RoundedTextEdit


class TranslatorView(BasePage):
    """翻译页面：纯界面壳，业务状态全部由外部注入"""

    PAGE_NAME = "translator"
    TITLE = "Translator"
    MODULE_NAME = "Translator"
    MODULE_ICON = translate_icon

    RESULT_TEXT_HEIGHT = 120

    # ==================== 界面 → 逻辑（controller 转接给 script）====================
    input_changed = Signal(str)  # 用户在输入框里编辑了文本
    translate_clicked = Signal()  # 点击翻译按钮
    cancel_clicked = Signal()  # 点击取消按钮
    swap_clicked = Signal()  # 点击交换语种按钮
    origin_lang_requested = Signal()  # 点击源语种按钮（请求语言网格）
    target_lang_requested = Signal()  # 点击目标语种按钮（请求语言网格）
    server_requested = Signal()  # 请求服务网格（右键菜单）
    origin_lang_selected = Signal(str)  # 语言网格选中
    target_lang_selected = Signal(str)
    server_selected = Signal(str)  # 服务网格选中（显示名）
    clear_requested = Signal()  # 页面退出清理
    back_requested = Signal()  # 返回（网格已收起时）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (400, 300)
        self._result_expanded = False

        layout = self.set_main_layout("v")
        assert layout is not None

        self.input_text = RoundedTextEdit(placeholder="Enter or paste text here...", parent=self)
        self.result_text = RoundedTextEdit(placeholder="Translation result", parent=self)
        self.result_text.setFixedHeight(0)

        self.selection_grid = SelectionGrid()
        # 点击网格项后，直接调用 grid 本身的收起逻辑
        self.selection_grid.item_selected.connect(lambda _: self.selection_grid.collapse())

        self.footer_layout = QHBoxLayout()
        self.footer_layout.addStretch()

        # 原语种按钮：启用原生 Checkable（选中态由 SelectionGrid 联动）
        self.origin_lang = CoreButton(text="")
        self.origin_lang.setCheckable(True)
        self.origin_lang.clicked.connect(self.origin_lang_requested.emit)
        self.footer_layout.addWidget(self.origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon)
        self.swap_btn.clicked.connect(self._on_swap_clicked)
        self.footer_layout.addWidget(self.swap_btn)

        # 目标语种按钮：启用原生 Checkable
        self.target_lang = CoreButton("")
        self.target_lang.setCheckable(True)
        self.target_lang.clicked.connect(self.target_lang_requested.emit)
        self.footer_layout.addWidget(self.target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.footer_layout.addStretch()

        # 翻译服务按钮：触发方式为右键，不干预选中状态，故不设 Checkable
        self.translation_server_btn = CoreButton("", bg_color="accent", parent=self)
        self.translation_server_btn.clicked.connect(self.translate_clicked.emit)
        self.translation_server_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.translation_server_btn.customContextMenuRequested.connect(self.server_requested.emit)
        self.footer_layout.addWidget(self.translation_server_btn)

        self.cancel_btn = CoreButton("Cancel", parent=self)
        self.cancel_btn.setBgColor("danger")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)
        self.footer_layout.addWidget(self.cancel_btn)

        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.addStretch()

        layout.addWidget(self.input_text)
        layout.addSpacing(4)
        layout.addWidget(self.result_text)
        layout.addSpacing(4)
        layout.addLayout(self.footer_layout)
        layout.addWidget(self.selection_grid)

        self.input_text.textChanged.connect(lambda: self.input_changed.emit(self.input_text.toPlainText()))

    # ==================== 渲染槽（controller → 界面）====================
    def set_input_text(self, text: str):
        with QSignalBlocker(self.input_text):  # 程序化回写不产生 input_changed，避免回声
            self.input_text.setPlainText(text)

    def set_result_text(self, text: str):
        self.result_text.setPlainText(text)

    def set_from_lang(self, lang: str):
        self.origin_lang.setText(lang)

    def set_to_lang(self, lang: str):
        self.target_lang.setText(lang)

    def set_server_display(self, display_name: str):
        self.translation_server_btn.setText(display_name)

    def set_translating(self, translating: bool):
        """翻译中：隐藏翻译按钮、显示取消按钮"""
        self.translation_server_btn.setVisible(not translating)
        self.cancel_btn.setVisible(translating)

    def set_result_expanded(self, expanded: bool):
        """结果区展开/收起（顺带收起网格，与原有动画行为一致）"""
        self._result_expanded = expanded
        target = self.RESULT_TEXT_HEIGHT if expanded else 0
        self.selection_grid.collapse(extra_animations=[(self.result_text, self.result_text.height(), target)])

    def focus_input(self):
        self.input_text.setFocus()

    # ==================== 网格呈现（controller 提供可选项与当前值）====================
    def open_origin_grid(self, items: list[str], current: str):
        self._open_grid(self.origin_lang, items, current, self.origin_lang.setText, self.origin_lang_selected)

    def open_target_grid(self, items: list[str], current: str):
        self._open_grid(self.target_lang, items, current, self.target_lang.setText, self.target_lang_selected)

    def open_server_grid(self, items: list[str], current: str):
        self._open_grid(
            self.translation_server_btn,
            items,
            current,
            self.translation_server_btn.setText,
            self.server_selected,
        )

    # ==================== 页面生命周期 ====================
    def clear_data(self):
        """退出页面：界面自行复位，业务状态清理交给 script（clear_requested）"""
        with QSignalBlocker(self.input_text):
            self.input_text.clear()
        self.result_text.clear()
        self.set_result_expanded(False)
        self.clear_requested.emit()

    def on_back_clicked(self):
        if self.selection_grid.is_expanded:
            self.selection_grid.collapse()
        else:
            self.back_requested.emit()

    # ==================== 内部方法 ====================
    def _open_grid(self, trigger_btn, items: list[str], current: str, apply_text, selected_signal):
        """展开网格：选中项立即回显到触发按钮，并把选中值广播出去"""
        # 展开网格时顺带收起结果区（原有视觉行为）
        extra = None
        if self._result_expanded:
            extra = [(self.result_text, self.result_text.height(), 0)]
            self._result_expanded = False

        def set_value(value: str):
            apply_text(value)
            selected_signal.emit(value)

        self.selection_grid.toggle(trigger_btn, items, current, set_value, extra)

    def _on_swap_clicked(self):
        """交换语种：按钮闪光是纯视觉反馈，就地完成；语种换算交给逻辑层"""
        self.origin_lang.flash()
        self.target_lang.flash()
        self.swap_clicked.emit()
