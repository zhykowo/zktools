import time

from pages.base_page import BasePage
from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget, QGridLayout
from PySide6.QtGui import QFont, QColor
from widgets.svg_button import SvgButton
from widgets.core_button import CoreButton
from widgets.text_editor import RoundedTextEdit
from core.page_router import page_router
from core.hotkey_manager import hotkey_manager

from resources.svgs import arrow_right_icon, translate_icon
from resources.colors import get_accent_color, get_purest_color, NEUTRAL_1, NEUTRAL_2
from resources.constants import CONFIG

from utils.translator import Translator
import utils.text_manager as text_manager

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
        # 替换旧动画组：stop 后 deleteLater 释放 C++ 对象，
        # 否则旧组因 parent 指向常驻页面而永不回收，每次交互累积泄漏
        if self._active_group is not None:
            self._active_group.stop()
            self._active_group.deleteLater()

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

class TranslationHotkey(QObject):
    """一键翻译全局热键

    按下快捷键后自动完成：复制选中文本 → 填入输入框 → 使用默认服务翻译。
    pynput 的回调运行在监听线程，不能直接操作 Qt 控件，
    因此通过信号以 QueuedConnection 转发到 Qt 主线程执行。
    """

    _triggered = Signal()

    def __init__(self, callback, hotkey: str = None, parent=None):
        super().__init__(parent)
        self._callback = callback
        self._hotkey = hotkey or CONFIG['translator'].get('hotkey', 'ctrl+shift+t')
        self._registered = False
        self._triggered.connect(self._run_in_main_thread, Qt.ConnectionType.QueuedConnection)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start(self):
        """注册全局热键并启动全局键盘监听（幂等）"""
        hotkey_manager.start()
        if hotkey_manager.register(self._hotkey, self._fire):
            self._registered = True
            print(f"[TranslationHotkey] 一键翻译已启用，快捷键: {self._hotkey}")
        else:
            print(f"[TranslationHotkey] 一键翻译快捷键 {self._hotkey} 注册失败！")

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
            text=self._text, server=self._server,
            from_lang=self._from_lang, to_lang=self._to_lang,
        )
        if not self._cancelled:
            self.translation_done.emit(result)

class TranslatorPage(BasePage):
    PAGE_NAME = "translator"
    TITLE = "Translator"
    MODULE_CENTER_NAME = "Translator"
    MODULE_CENTER_ICON = translate_icon

    SUPPORTED_LANGUAGES = [
        "Auto", "English", "Chinese",
        "Japanese", "Korean", "French",
        "German", "Spanish", "Russian"
    ]
    SUPPORTED_SERVERS = [
        "Google", "DeepL", "Baidu",
        "Bing", "AI1", "AI2"
    ]

    GRID_ITEM_HEIGHT = 36
    GRID_SPACING = 8
    RESULT_TEXT_HEIGHT = 120
    # 取消按钮配色（红色）
    CANCEL_COLOR = QColor(214, 69, 65)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.translator = Translator()
        self.animator = _Animator(self)
        self.target_size = (400, 300)

        # 后台翻译线程状态
        self._worker = None
        self._translation_cancelled = False

        # 当前展开的网格类型状态
        self._current_grid_mode = GridMode.NONE

        layout = self.set_main_layout('v')

        # 配色：激活态使用 accent 高亮，非激活态使用灰色（参考 text_editor 的暗灰配色）
        self.accent_qcolor = get_purest_color(get_accent_color())
        self.idle_btn_bg = NEUTRAL_2

        # 2. 文本输入框与结果框（圆角背景 + accent/灰色状态边框 + placeholder）
        self.input_text = RoundedTextEdit(placeholder='Enter or paste text here...', bg_color=NEUTRAL_1, parent=self)
        self.result_text = RoundedTextEdit(placeholder='Translation result', bg_color=NEUTRAL_1, radius=10, parent=self)

        font = QFont()
        font.setPointSize(12)
        self.input_text.setFont(font)
        self.result_text.setFont(font)

        self.result_text.setMinimumHeight(0)
        self.result_text.setMaximumHeight(0)

        # 3. 通用平铺网格选择面板
        self.selection_grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.selection_grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 10)
        self.grid_layout.setSpacing(self.GRID_SPACING)

        self.selection_grid_widget.setMinimumHeight(0)
        self.selection_grid_widget.setMaximumHeight(0)

        # 4. 底部控制栏
        self.footer_layout = QHBoxLayout()

        self.footer_layout.addStretch()

        self.origin_lang = CoreButton(text=CONFIG['translator']['default_from_lang'])
        self.origin_lang.clicked.connect(lambda: self.display_lang_list("origin"))
        self.footer_layout.addWidget(self.origin_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.swap_btn = SvgButton(self, icon_size=24, svg_data=arrow_right_icon)
        self.swap_btn.clicked.connect(self._swap_languages)
        self.footer_layout.addWidget(self.swap_btn)

        self.target_lang = CoreButton(CONFIG['translator']['default_to_lang'])
        self.target_lang.clicked.connect(lambda: self.display_lang_list("target"))
        self.footer_layout.addWidget(self.target_lang, alignment=Qt.AlignmentFlag.AlignCenter)

        self.footer_layout.addStretch()

        # 默认服务：config 指定内部标识符，按钮文本显示 config 中配置的名称
        default_server = CONFIG['translator'].get('default_server', 'Baidu')
        self._current_server = default_server if default_server in self.SUPPORTED_SERVERS else self.SUPPORTED_SERVERS[0]

        self.translation_server_btn = CoreButton(self._server_display_name(self._current_server), parent=self)
        self.translation_server_btn.clicked.connect(self._start_translation)
        self.translation_server_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.translation_server_btn.customContextMenuRequested.connect(self.display_server_list)
        self.footer_layout.addWidget(self.translation_server_btn)

        # 取消按钮：与翻译按钮共存于布局，翻译时通过 hide/show 切换显示，
        # 隐藏的组件会自动空出布局位置，无需移除/插入操作
        self.cancel_btn = CoreButton('Cancel', parent=self)
        self.cancel_btn.setBgColor(self.CANCEL_COLOR)
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_translation)
        self.footer_layout.addWidget(self.cancel_btn)

        self.footer_layout.addStretch()
        
        # 布局组织
        layout.addWidget(self.input_text)
        layout.addWidget(self.result_text)
        layout.addLayout(self.footer_layout)
        layout.addWidget(self.selection_grid_widget)
        layout.addStretch()

        # 初始状态：网格未展开，from/to 语言按钮均置为灰色（否则默认 accent 高亮）
        self._set_lang_buttons_active(GridMode.NONE)

        # 一键翻译：注册全局热键（复制选中文本 → 填入输入框 → 默认服务翻译）
        self.one_click_hotkey = TranslationHotkey(self._on_one_click_translate, parent=self)
        self.one_click_hotkey.start()

    def on_show(self):
        tm = text_manager.get()
        now_time = time.perf_counter()
        elapsed = now_time - tm.selection_time
        if elapsed <= 10 and self.input_text.toPlainText() == '':
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
            print("[TranslatorPage] 未获取到选中的文本，一键翻译已取消")
            return

        # 1. 切换到翻译页并展示选中文本
        page_router.immediate_switch("translator")
        self.input_text.setText(selected)
        self.input_text.setFocus()

        self.origin_lang.setText(CONFIG['translator']['default_from_lang'],)
        self.target_lang.setText(CONFIG['translator']['default_to_lang'])

        # 2. 使用默认服务与默认语言执行翻译
        default_server = CONFIG['translator'].get('default_server', 'Baidu')
        self._current_server = default_server if default_server in self.SUPPORTED_SERVERS else self.SUPPORTED_SERVERS[0]
        self.translation_server_btn.setText(self._server_display_name(self._current_server))
        self._start_translation()


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
        self._set_lang_buttons_active(mode)
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
        self._set_lang_buttons_active(GridMode.NONE)
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
            # 仅当前选中项（激活）以 accent 高亮，其余显示灰色
            if text != current_value:
                btn.setBgColor(self.idle_btn_bg)
            
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

    def _server_display_name(self, server_id):
        """服务按钮显示名：AI1/AI2 使用 config 中指定的名称，其余显示自身标识符"""
        if server_id in ('AI1', 'AI2'):
            name = CONFIG['translator'].get('apis', {}).get('ai', {}).get(server_id, {}).get('name')
            return name or server_id
        return server_id

    def display_server_list(self):
        """显示翻译服务选择网格（AI1/AI2 显示 config 指定的名称，其余显示自身名称）"""
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

        self._request_grid_switch(GridMode.SERVER, items, current_display, set_server)

    def _start_translation(self):
        """后台线程执行翻译，避免阻塞 UI；翻译期间按钮替换为红色 Cancel 按钮"""
        if self._worker is not None:
            return  # 已有翻译进行中（此时按钮已变为 Cancel，点击即取消）

        text = self.input_text.toPlainText()
        server = self._current_server
        from_lang = self.origin_lang.text()
        to_lang = self.target_lang.text()

        print(f"正在使用 [{server}] 将 '{text}' 从 {from_lang} 翻译为 {to_lang}...")

        self._translation_cancelled = False
        self._set_translating(True)

        self._worker = TranslationWorker(
            translator=self.translator,
            text=text, server=server,
            from_lang=from_lang, to_lang=to_lang,
            parent=self,
        )
        self._worker.translation_done.connect(self._on_translation_done)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _set_translating(self, translating: bool):
        """翻译中显示红色 Cancel 按钮、隐藏翻译按钮；结束时反向。

        隐藏的组件会自动空出布局位置并触发重排，两个按钮在布局中
        始终占据同一槽位，因此无需移除/插入即可完成切换。
        """
        self.translation_server_btn.setVisible(not translating)
        self.cancel_btn.setVisible(translating)

    def _cancel_translation(self):
        """取消进行中的翻译：丢弃结果并立即恢复翻译按钮（同步请求无法中断网络传输）"""
        self._translation_cancelled = True
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            # 线程结束后自动释放，避免 QThread 对象泄漏
            worker.finished.connect(worker.deleteLater)
        self._set_translating(False)

    def _on_translation_done(self, result):
        """翻译完成（主线程）：显示结果并展开结果框"""
        if self._translation_cancelled:
            self._translation_cancelled = False
            return

        self.result_text.setText(result)

        self._current_grid_mode = GridMode.NONE
        self._set_lang_buttons_active(GridMode.NONE)

        grid_start_h = self.selection_grid_widget.height()
        result_start_h = self.result_text.height()

        self.animator.animate_heights([
            (self.selection_grid_widget, grid_start_h, 0),
            (self.result_text, result_start_h, self.RESULT_TEXT_HEIGHT)
        ])
        self._set_translating(False)

    def _on_worker_finished(self):
        """后台线程自然结束（未被取消）：释放 worker"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _set_lang_buttons_active(self, mode: GridMode):
        """仅当对应语言网格展开时，from/to 语言按钮才以 accent 高亮，否则显示灰色"""
        self.origin_lang.setBgColor(self.accent_qcolor if mode == GridMode.ORIGIN_LANG else self.idle_btn_bg)
        self.target_lang.setBgColor(self.accent_qcolor if mode == GridMode.TARGET_LANG else self.idle_btn_bg)

    def _swap_languages(self):
        """互换源语言与目标语言"""
        temp = self.origin_lang.text()
        self.origin_lang.setText(self.target_lang.text())
        self.target_lang.setText(temp)

    def on_back_clicked(self):
        """返回逻辑：如果网格开启则收起，否则退出页面"""
        if self._current_grid_mode != GridMode.NONE:
            self._collapse_grid()
        else:
            page_router.exit_self(self.page_name)

    def clear_data(self):
        self._cancel_translation()
        self.input_text.setText('')
        self.result_text.setText('')

        self._set_lang_buttons_active(GridMode.NONE)

        self.animator.animate_heights([
            (self.selection_grid_widget, self.selection_grid_widget.height(), 0),
            (self.result_text, self.result_text.height(), 0)
        ])