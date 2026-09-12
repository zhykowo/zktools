# translator_page.py
import logging

logger = logging.getLogger(__name__)
import time
from enum import Enum, auto
from typing import ClassVar

from PySide6.QtCore import (
    QObject,
    Qt,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QHBoxLayout

from core.hotkey_manager import hotkey_manager
from core.page_router import page_router
from pages.base_page import BasePage
from resources.constants import CONFIG
from resources.svgs import arrow_right_icon, translate_icon
from utils import text_manager
from utils.translator import Translator
from widgets.core_button import CoreButton
from widgets.selection_grid import SelectionGrid
from widgets.svg_button import SvgButton
from widgets.text_editor import RoundedTextEdit


class _GlobalSignals(QObject):
    translate_shortcut_signal = Signal(str)


# 模块级单例
translation_global_signals = _GlobalSignals()


class TranslationHotkey(QObject):
    """一键翻译全局热键

    按下快捷键后自动完成：复制选中文本 → 填入输入框 → 使用默认服务翻译。
    pynput 的回调运行在监听线程，不能直接操作 Qt 控件，
    因此通过信号以 QueuedConnection 转发到 Qt 主线程执行。
    """

    _triggered = Signal()

    def __init__(self, callback, hotkey: str | None = None, parent=None):
        super().__init__(parent)
        self._callback = callback
        self._hotkey = hotkey or CONFIG["translator"].get("hotkey", "ctrl+shift+t")
        self._registered = False
        self._triggered.connect(self._run_in_main_thread, Qt.ConnectionType.QueuedConnection)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start(self):
        """注册全局热键并启动全局键盘监听（幂等）"""
        if hotkey_manager.register(self._hotkey, self._fire):
            self._registered = True
            logger.info(f"[TranslationHotkey] 一键翻译已启用，快捷键: {self._hotkey}")
        else:
            logger.error(f"[TranslationHotkey] 一键翻译快捷键 {self._hotkey} 注册失败！")

    def stop(self):
        """注销全局热键"""
        if self._registered:
            hotkey_manager.unregister(self._hotkey)
            self._registered = False

    def _fire(self):
        """pynput 监听线程回调：仅转发信号，不做任何 Qt 操作"""
        self._triggered.emit()

    @Slot()
    def _run_in_main_thread(self):
        """Qt 主线程中执行实际的一键翻译流程"""
        if self._callback:
            self._callback()


class TranslationWorker(QThread):
    """后台翻译线程

    translate_text 是同步阻塞调用（含网络请求），直接在主线程执行会卡死 UI。
    放入 QThread 执行，完成后通过信号把结果回传主线程；
    调用 cancel() 后结果将被丢弃，不再更新界面。
    """

    translation_done = Signal(object)

    def __init__(self, translator, text, server, from_lang, to_lang, parent=None):
        super().__init__(parent)
        self._translator = translator
        self._text = text
        self._server = server
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._cancelled = False

    def cancel(self):
        """请求取消：置标志，翻译结果将被丢弃（同步请求无法中断网络传输）"""
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return
        result = self._translator.translate_text(
            text=self._text,
            server=self._server,
            from_lang=self._from_lang,
            to_lang=self._to_lang,
        )
        if not self._cancelled:
            self.translation_done.emit(result)


class TranslatorPage(BasePage):
    PAGE_NAME = "translator"
    TITLE = "Translator"
    MODULE_NAME = "Translator"
    MODULE_ICON = translate_icon

    SUPPORTED_LANGUAGES: ClassVar[list[str]] = [
        "Auto",
        "English",
        "Chinese",
        "Japanese",
        "Korean",
        "French",
        "German",
        "Spanish",
        "Russian",
    ]
    SUPPORTED_SERVERS: ClassVar[list[str]] = ["Google", "DeepL", "Baidu", "Bing", "AI1", "AI2"]

    RESULT_TEXT_HEIGHT = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.translator = Translator()
        self.target_size = (400, 300)

        self._worker = None
        self._translation_cancelled = False
        self._server_display_to_id: dict[str, str] = {}

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

        # 原语种按钮：启用原生 Checkable
        self.origin_lang = CoreButton(text=CONFIG["translator"]["default_from_lang"])
        self.origin_lang.setCheckable(True)
        self.origin_lang.clicked.connect(lambda: self.display_lang_list("origin"))
        self.footer_layout.addWidget(self.origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon)
        self.swap_btn.clicked.connect(self._swap_languages)
        self.footer_layout.addWidget(self.swap_btn)

        # 目标语种按钮：启用原生 Checkable
        self.target_lang = CoreButton(CONFIG["translator"]["default_to_lang"])
        self.target_lang.setCheckable(True)
        self.target_lang.clicked.connect(lambda: self.display_lang_list("target"))
        self.footer_layout.addWidget(self.target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.footer_layout.addStretch()

        default_server = CONFIG["translator"].get("default_server", "Baidu")
        self._current_server = default_server if default_server in self.SUPPORTED_SERVERS else self.SUPPORTED_SERVERS[0]

        # 翻译服务按钮：因为触发方式是右键不干预选中状态，不在配置里设 Checkable
        self.translation_server_btn = CoreButton(
            self._server_display_name(self._current_server),
            bg_color="accent",
            parent=self,
        )
        self.translation_server_btn.clicked.connect(self._start_translation)
        self.translation_server_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.translation_server_btn.customContextMenuRequested.connect(self.display_server_list)
        self.footer_layout.addWidget(self.translation_server_btn)

        self.cancel_btn = CoreButton("Cancel", parent=self)
        self.cancel_btn.setBgColor("danger")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_translation)
        self.footer_layout.addWidget(self.cancel_btn)

        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.addStretch()

        layout.addWidget(self.input_text)
        layout.addSpacing(4)
        layout.addWidget(self.result_text)
        layout.addSpacing(4)
        layout.addLayout(self.footer_layout)
        layout.addWidget(self.selection_grid)

        self.one_click_hotkey = TranslationHotkey(self._on_one_click_translate, parent=self)
        self.one_click_hotkey.start()

        translation_global_signals.translate_shortcut_signal.connect(self.translate_shortcut)

    def on_show(self):
        tm = text_manager.get()
        now_time = time.perf_counter()
        elapsed = now_time - tm.selection_time
        if elapsed <= 10 and self.input_text.toPlainText() == "":
            selected_text = tm.selected_text
            if selected_text:
                self.input_text.setText(selected_text)
            elif (now_time - tm.copy_time) <= 10:
                self.input_text.setText(tm.clipboard_text)

    def _on_one_click_translate(self):
        """一键翻译：复制选中文本 → 填入输入框 → 使用默认服务翻译"""
        tm = text_manager.get()
        selected = tm.copy_selected_text()
        if not selected:
            logger.info("[TranslatorPage] 未获取到选中的文本，一键翻译已取消")
            return
        self.translate_shortcut(text=selected)

    def translate_shortcut(self, text: str):
        # 1. 切换到翻译页并展示选中文本
        page_router.immediate_switch("translator")
        self.input_text.setText(text)
        self.input_text.setFocus()

        self.origin_lang.setText(
            CONFIG["translator"]["default_from_lang"],
        )
        self.target_lang.setText(CONFIG["translator"]["default_to_lang"])

        # 2. 使用默认服务与默认语言执行翻译
        default_server = CONFIG["translator"].get("default_server", "Baidu")
        self._current_server = default_server if default_server in self.SUPPORTED_SERVERS else self.SUPPORTED_SERVERS[0]
        self.translation_server_btn.setText(self._server_display_name(self._current_server))
        self._start_translation()

    # ==================== 网格切换核心逻辑 ====================
    def display_lang_list(self, target_type="origin"):
        """一句话调度网格呈现，UI与状态交由SelectionGrid自动处理"""
        trigger_btn = self.origin_lang if target_type == "origin" else self.target_lang
        current_lang = trigger_btn.text()

        def set_language(selected_lang):
            trigger_btn.setText(selected_lang)

        extra = [(self.result_text, self.result_text.height(), 0)] if self.result_text.height() > 0 else None
        self.selection_grid.toggle(trigger_btn, self.SUPPORTED_LANGUAGES, current_lang, set_language, extra)

    def display_server_list(self):
        items = []
        self._server_display_to_id = {}
        for server_id in self.SUPPORTED_SERVERS:
            display_name = self._server_display_name(server_id)
            self._server_display_to_id[display_name] = server_id
            items.append(display_name)

        current_display = self._server_display_name(self._current_server)

        def set_server(selected_display):
            self._current_server = self._server_display_to_id[selected_display]
            self.translation_server_btn.setText(selected_display)

        extra = [(self.result_text, self.result_text.height(), 0)] if self.result_text.height() > 0 else None
        self.selection_grid.toggle(self.translation_server_btn, items, current_display, set_server, extra)

    # ==================== 杂项 ====================

    def _server_display_name(self, server_id):
        if server_id in ("AI1", "AI2"):
            name = CONFIG["translator"].get("apis", {}).get("ai", {}).get(server_id, {}).get("name")
            return name or server_id
        return server_id

    def _start_translation(self):
        if self._worker is not None:
            return

        text = self.input_text.toPlainText()
        server = self._current_server
        from_lang = self.origin_lang.text()
        to_lang = self.target_lang.text()

        logger.info(f"正在使用 [{server}] 将 '{text}' 从 {from_lang} 翻译为 {to_lang}...")

        self._translation_cancelled = False
        self._set_translating(True)

        self._worker = TranslationWorker(
            translator=self.translator,
            text=text,
            server=server,
            from_lang=from_lang,
            to_lang=to_lang,
            parent=self,
        )
        self._worker.translation_done.connect(self._on_translation_done)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _set_translating(self, translating: bool):
        self.translation_server_btn.setVisible(not translating)
        self.cancel_btn.setVisible(translating)

    def _cancel_translation(self):
        self._translation_cancelled = True
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            worker.finished.connect(worker.deleteLater)
        self._set_translating(False)

    def _on_translation_done(self, result):
        if self._translation_cancelled:
            self._translation_cancelled = False
            return

        self.result_text.setText(result)
        # 直接通知网格收起自身即可
        self.selection_grid.collapse(extra_animations=[(self.result_text, self.result_text.height(), self.RESULT_TEXT_HEIGHT)])
        self._set_translating(False)

    def _on_worker_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _swap_languages(self):
        temp = self.origin_lang.text()
        self.origin_lang.setText(self.target_lang.text())
        self.target_lang.setText(temp)

    def on_back_clicked(self):
        if self.selection_grid.is_expanded:
            self.selection_grid.collapse()
        else:
            page_router.exit_self(self.page_name)

    def clear_data(self):
        self._cancel_translation()
        self.input_text.setText("")
        self.result_text.setText("")

        self.selection_grid.collapse(extra_animations=[(self.result_text, self.result_text.height(), 0)])
