"""翻译模块 —— 逻辑层（script）

负责翻译模块的全部状态与流程：语种 / 服务选择、待翻译文本、翻译任务的
发起与取消、一键翻译（复制 → 剪贴板取文本 → 翻译）的编排。

硬约束（这是本文件能脱离界面独立单测的前提）：

- 不 import 任何 QWidget / BasePage / pages.*，也不被 view 反向依赖；
- 不直接调用 hotkey_manager / clipboard_monitor / page_router，
  需要这些副作用时只发信号（copy_shortcut_requested / activate_requested），
  由 controller 在组合层落地真实调用；
- 翻译执行器（runner）可注入，单测替换为同步执行器即可，无需事件循环；
- 对外只有「信号出 + 方法进」两种接口，调用方无需知道界面长什么样。
"""

import logging
from typing import ClassVar

from PySide6.QtCore import QObject, QThread, Signal

from resources.constants import CONFIG
from utils.translator import Translator

logger = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """后台翻译线程

    translate_text 是同步阻塞调用（含网络请求），直接在主线程执行会卡死 UI。
    完成后通过信号把结果回传主线程；调用 cancel() 后结果将被丢弃。
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


class QtTranslationRunner(QObject):
    """默认翻译执行器：把阻塞的 translate_text 放进 QThread

    对 script 暴露统一的三件套接口：start() / cancel() / cleanup()，
    结果通过 finished(result) 信号回传。
    """

    finished = Signal(object)

    def __init__(self, translator, text, server, from_lang, to_lang, parent=None):
        super().__init__(parent)
        self._worker = TranslationWorker(translator, text, server, from_lang, to_lang, parent=self)
        self._worker.translation_done.connect(self._on_worker_done)
        self._cleaned = False

    def start(self):
        self._worker.start()

    def cancel(self):
        self._worker.cancel()

    def cleanup(self):
        """断开结果回传并安排线程对象释放（可重复调用）"""
        if self._cleaned:
            return
        self._cleaned = True
        try:
            self._worker.translation_done.disconnect(self._on_worker_done)
        except (RuntimeError, TypeError):  # 已断开 / 对象已销毁
            pass
        self._worker.finished.connect(self._worker.deleteLater)

    def _on_worker_done(self, result):
        self.finished.emit(result)


class SyncTranslationRunner(QObject):
    """同步翻译执行器：单测 / 无事件循环环境下注入使用

    start() 内直接完成翻译并立即回传结果，行为与 QtTranslationRunner 一致，
    只是不经过线程，便于断言。
    """

    finished = Signal(object)

    def __init__(self, translator, text, server, from_lang, to_lang, parent=None):
        super().__init__(parent)
        self._translator = translator
        self._text = text
        self._server = server
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._cancelled = False

    def start(self):
        if self._cancelled:
            return
        self.finished.emit(
            self._translator.translate_text(
                text=self._text,
                server=self._server,
                from_lang=self._from_lang,
                to_lang=self._to_lang,
            )
        )

    def cancel(self):
        self._cancelled = True

    def cleanup(self):
        pass


class TranslatorScript(QObject):
    """翻译模块的纯逻辑核心

    对外接口分两类：
    - 信号（出）：状态变化广播，controller 转接到 view / 外部服务；
    - 方法（进）：set_* / request_* / submit_* 等入口，controller 调用。

    内部状态是唯一事实来源，界面只是它的渲染结果。
    """

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

    # ==================== 逻辑 → 界面（controller 转接给 view）====================
    input_text_changed = Signal(str)  # 输入文本被脚本改写（如剪贴板回填）
    result_text_changed = Signal(str)  # 翻译结果
    from_lang_changed = Signal(str)  # 源语种
    to_lang_changed = Signal(str)  # 目标语种
    server_changed = Signal(str)  # 翻译服务显示名
    translating_changed = Signal(bool)  # 翻译中 / 空闲
    result_panel_requested = Signal(bool)  # 结果区展开 / 收起
    input_focus_requested = Signal()  # 请求聚焦输入框

    # ==================== 逻辑 → 外部服务（controller 落地真实调用）====================
    activate_requested = Signal()  # 请求切换到翻译页
    copy_shortcut_requested = Signal(str)  # 请求模拟复制快捷键（如 ctrl+c）

    def __init__(self, translator=None, runner_factory=QtTranslationRunner, parent=None):
        super().__init__(parent)
        # 依赖注入：translator 可换成假实现，runner_factory 可换成同步执行器
        self._translator = translator if translator is not None else Translator()
        self._runner_factory = runner_factory

        config = CONFIG["translator"]
        self._from_lang = config.get("default_from_lang", "Auto")
        self._to_lang = config.get("default_to_lang", "Chinese")
        self._server = self._normalize_server(config.get("default_server"))

        self._input_text = ""
        self._result_text = ""
        self._translating = False
        self._pending_one_click = False
        self._runner = None

    # ==================== 只读状态（供 controller / 单测读取）====================
    @property
    def input_text(self) -> str:
        return self._input_text

    @property
    def result_text(self) -> str:
        return self._result_text

    @property
    def from_lang(self) -> str:
        return self._from_lang

    @property
    def to_lang(self) -> str:
        return self._to_lang

    @property
    def server(self) -> str:
        """当前服务标识（如 Baidu / AI1）"""
        return self._server

    @property
    def server_display(self) -> str:
        """当前服务显示名（AI1/AI2 取配置里的 name）"""
        return self._server_display_name(self._server)

    @property
    def is_translating(self) -> bool:
        return self._translating

    # ==================== 状态广播 ====================
    def emit_state(self):
        """广播当前完整状态（controller 接线完成后调用一次，用于界面首次渲染）"""
        self.input_text_changed.emit(self._input_text)
        self.result_text_changed.emit(self._result_text)
        self.from_lang_changed.emit(self._from_lang)
        self.to_lang_changed.emit(self._to_lang)
        self.server_changed.emit(self.server_display)
        self.translating_changed.emit(self._translating)

    # ==================== 界面可选项 ====================
    def language_items(self) -> list[str]:
        """语种网格的可选项"""
        return list(self.SUPPORTED_LANGUAGES)

    def server_items(self) -> list[str]:
        """服务网格的可选项（显示名，AI 服务取配置 name）"""
        return [self._server_display_name(s) for s in self.SUPPORTED_SERVERS]

    # ==================== 用户操作入口 ====================
    def set_input_text(self, text: str):
        # 值未变化时不再广播：避免「脚本写界面 → 界面回传 → 脚本再写」的回声循环
        if text == self._input_text:
            return
        self._input_text = text
        self.input_text_changed.emit(text)

    def set_from_lang(self, lang: str):
        if lang == self._from_lang:
            return
        self._from_lang = lang
        self.from_lang_changed.emit(lang)

    def set_to_lang(self, lang: str):
        if lang == self._to_lang:
            return
        self._to_lang = lang
        self.to_lang_changed.emit(lang)

    def set_server(self, display_name: str):
        """按显示名切换服务（显示名 → 服务标识的映射由本层持有）"""
        server_id = self._server_id_map().get(display_name)
        if server_id is None or server_id == self._server:
            return
        self._server = server_id
        self.server_changed.emit(display_name)

    def swap_languages(self):
        """交换源/目标语种；源为 Auto 时目标回落 English（无法译向"自动"）"""
        old_from = self._from_lang
        self.set_from_lang(self._to_lang)
        self.set_to_lang("English" if old_from == "Auto" else old_from)

    def request_translation(self):
        """发起翻译：使用当前输入文本、语种与服务"""
        if self._runner is not None:
            return  # 已有任务在跑，忽略重复点击

        logger.info(
            "正在使用 [%s] 将 '%s' 从 %s 翻译为 %s...",
            self._server,
            self._input_text,
            self._from_lang,
            self._to_lang,
        )

        self._set_translating(True)
        runner = self._runner_factory(
            self._translator,
            self._input_text,
            self._server,
            self._from_lang,
            self._to_lang,
            parent=self,
        )
        runner.finished.connect(self._on_translation_done)
        self._runner = runner
        runner.start()

    def cancel_translation(self):
        """取消当前翻译任务：丢弃结果并释放执行器"""
        runner = self._runner
        self._runner = None
        if runner is not None:
            try:
                runner.finished.disconnect(self._on_translation_done)
            except (RuntimeError, TypeError):  # 已断开 / 对象已销毁
                pass
            runner.cancel()
            runner.cleanup()
        self._set_translating(False)

    def reset(self):
        """清空模块数据（页面退出时调用）"""
        self.cancel_translation()
        self._pending_one_click = False
        self.set_input_text("")
        self._result_text = ""
        self.result_text_changed.emit("")
        self.result_panel_requested.emit(False)

    def shutdown(self):
        """模块销毁：停止在途任务，注销一键翻译等待态"""
        self.cancel_translation()
        self._pending_one_click = False

    # ==================== 一键翻译流程 ====================
    def one_click_triggered(self):
        """一键翻译热键触发：只请求复制，文本由剪贴板回调送回"""
        self._pending_one_click = True
        self.copy_shortcut_requested.emit("ctrl+c")

    def on_clipboard_text(self, text: str):
        """剪贴板回调：仅在等待一键翻译时消费文本"""
        if not self._pending_one_click:
            return
        self._pending_one_click = False
        if not text:
            logger.info("未获取到文本，一键翻译已取消")
            return
        self.submit_external_text(text)

    def submit_external_text(self, text: str):
        """外部文本进入翻译（一键翻译 / 其他模块调用）

        流程：切到翻译页 → 回填输入框并聚焦 → 复位为默认语种与服务 → 翻译。
        """
        self._input_text = text
        self.input_text_changed.emit(text)
        self.activate_requested.emit()
        self.input_focus_requested.emit()

        config = CONFIG["translator"]
        self._from_lang = config.get("default_from_lang", "Auto")
        self._to_lang = config.get("default_to_lang", "Chinese")
        self.from_lang_changed.emit(self._from_lang)
        self.to_lang_changed.emit(self._to_lang)

        self._server = self._normalize_server(config.get("default_server"))
        self.server_changed.emit(self.server_display)

        self.request_translation()

    # ==================== 内部方法 ====================
    def _on_translation_done(self, result):
        runner = self._runner
        if runner is None:
            return  # 已被取消，丢弃迟到的结果
        self._runner = None
        runner.cleanup()

        self._result_text = result
        self.result_text_changed.emit(result)
        self.result_panel_requested.emit(True)
        self._set_translating(False)

    def _set_translating(self, translating: bool):
        self._translating = translating
        self.translating_changed.emit(translating)

    @staticmethod
    def _normalize_server(server_id) -> str:
        """配置里的服务名不可用时回落首个受支持服务"""
        return server_id if server_id in TranslatorScript.SUPPORTED_SERVERS else TranslatorScript.SUPPORTED_SERVERS[0]

    def _server_id_map(self) -> dict[str, str]:
        """显示名 → 服务标识"""
        return {self._server_display_name(s): s for s in self.SUPPORTED_SERVERS}

    @staticmethod
    def _server_display_name(server_id: str) -> str:
        if server_id in ("AI1", "AI2"):
            name = CONFIG["translator"].get("apis", {}).get("ai", {}).get(server_id, {}).get("name")
            return name or server_id
        return server_id
