"""翻译模块 —— 调度层（controller）

组合根：script 与 view 彼此不知道对方存在，全部连线在此完成；
与外部服务（页面路由 / 全局热键 / 剪贴板 / 全局信号总线）的耦合也收敛在此。

- view 的用户意图信号 → script 的入口方法
- script 的状态广播 → view 的渲染槽
- script 的副作用请求 → 真实调用（page_router / hotkey_manager）
- 外部入口（其他模块的一键翻译请求、剪贴板回调）→ script

因为连线集中在一处，界面可以被整体释放（detach_view）或替换（attach_view），
逻辑层照常运行；反过来逻辑层也能在没有界面的情况下被驱动与断言。
"""

import logging

from core.hotkey_manager import hotkey_manager
from core.page_router import page_router
from core.signal import global_signals
from modules.translator.script import TranslatorScript
from modules.translator.view import TranslatorView
from resources.constants import CONFIG
from utils import clipboard_monitor

logger = logging.getLogger(__name__)


class TranslatorController:
    """翻译模块调度器：持有 script 与 view，并负责二者之间的一切转接"""

    PAGE_NAME = TranslatorView.PAGE_NAME

    def __init__(self, script=None, view=None, parent=None, enable_hotkey: bool = True):
        self.script = script if script is not None else TranslatorScript()
        self.view = None
        self._enable_hotkey = enable_hotkey
        self._hotkey = CONFIG["translator"].get("hotkey") or "ctrl+shift+t"
        self._hotkey_registered = False

        # 界面相关连线（detach_view 时整体摘除）
        self._view_links: list[tuple] = []
        # 逻辑/外部连线（与界面无关，生命周期跟随 controller）
        self._core_links: list[tuple] = []

        self._wire_script()
        self.attach_view(view if view is not None else TranslatorView(parent))
        self._wire_external()
        if self._enable_hotkey:
            self._register_hotkey()

    # ==================== 对外入口 ====================
    @property
    def page(self) -> TranslatorView | None:
        """供 main.py 注册到页面路由的界面实例"""
        return self.view

    def shutdown(self):
        """模块销毁：注销热键、停止在途任务、断开全部连线"""
        if self._hotkey_registered:
            hotkey_manager.unregister(self._hotkey)
            self._hotkey_registered = False
        self.script.shutdown()
        self.detach_view()
        self._unlink(self._core_links)

    # ==================== 界面挂载 / 卸载 ====================
    def attach_view(self, view):
        """挂载界面并完成双向连线；view 为 None 表示仅保留逻辑层

        可重复调用以替换界面；挂载后会把 script 的当前状态整体推送一次。
        """
        self.detach_view()
        if view is None:
            return None

        self.view = view
        script = self.script

        # ---- 界面 → 逻辑 ----
        self._link_view(view.input_changed, script.set_input_text)
        self._link_view(view.translate_clicked, script.request_translation)
        self._link_view(view.cancel_clicked, script.cancel_translation)
        self._link_view(view.swap_clicked, script.swap_languages)
        self._link_view(view.clear_requested, script.reset)
        self._link_view(view.back_requested, self._on_back_requested)
        self._link_view(view.origin_lang_requested, self._on_origin_lang_requested)
        self._link_view(view.target_lang_requested, self._on_target_lang_requested)
        self._link_view(view.server_requested, self._on_server_requested)
        self._link_view(view.origin_lang_selected, script.set_from_lang)
        self._link_view(view.target_lang_selected, script.set_to_lang)
        self._link_view(view.server_selected, script.set_server)

        # ---- 逻辑 → 界面 ----
        self._link_view(script.input_text_changed, view.set_input_text)
        self._link_view(script.result_text_changed, view.set_result_text)
        self._link_view(script.from_lang_changed, view.set_from_lang)
        self._link_view(script.to_lang_changed, view.set_to_lang)
        self._link_view(script.server_changed, view.set_server_display)
        self._link_view(script.translating_changed, view.set_translating)
        self._link_view(script.result_panel_requested, view.set_result_expanded)
        self._link_view(script.input_focus_requested, view.focus_input)

        script.emit_state()  # 首帧渲染
        return view

    def detach_view(self):
        """卸载并释放界面：连线全部摘除，script 仍可独立运行"""
        view = self.view
        self._unlink(self._view_links)
        self.view = None
        return view

    # ==================== 外部服务接线 ====================
    def _wire_script(self):
        """script 的副作用请求 → 真实调用"""
        self._link_core(self.script.activate_requested, self._activate_page)
        self._link_core(self.script.copy_shortcut_requested, self._trigger_copy)

    def _wire_external(self):
        """外部入口 → script"""
        self._link_core(global_signals.translate_shortcut, self.script.submit_external_text)
        try:
            monitor = clipboard_monitor.get()
        except RuntimeError:
            logger.warning("[TranslatorController] 剪贴板监听尚未初始化，一键翻译暂不可用")
        else:
            self._link_core(monitor.cbChanged, self.script.on_clipboard_text)

    def _register_hotkey(self):
        """注册一键翻译全局热键"""
        if hotkey_manager.register(self._hotkey, self.script.one_click_triggered):
            self._hotkey_registered = True
            logger.info("[TranslatorController] 一键翻译已启用，快捷键: %s", self._hotkey)
        else:
            logger.error("[TranslatorController] 一键翻译快捷键 %s 注册失败！", self._hotkey)

    # ==================== 信号转接槽 ====================
    def _activate_page(self):
        page_router.immediate_switch(self.PAGE_NAME)

    def _trigger_copy(self, hotkey: str):
        hotkey_manager.trigger(hotkey)

    def _on_back_requested(self):
        page_router.exit_self(self.view.page_name if self.view is not None else self.PAGE_NAME)

    def _on_origin_lang_requested(self):
        if self.view is not None:
            self.view.open_origin_grid(self.script.language_items(), self.script.from_lang)

    def _on_target_lang_requested(self):
        if self.view is not None:
            self.view.open_target_grid(self.script.language_items(), self.script.to_lang)

    def _on_server_requested(self):
        if self.view is not None:
            self.view.open_server_grid(self.script.server_items(), self.script.server_display)

    # ==================== 连线工具 ====================
    def _link_view(self, signal, slot):
        self._connect(self._view_links, signal, slot)

    def _link_core(self, signal, slot):
        self._connect(self._core_links, signal, slot)

    @staticmethod
    def _connect(bucket: list[tuple], signal, slot):
        signal.connect(slot)
        bucket.append((signal, slot))
        return bucket

    @staticmethod
    def _unlink(bucket: list[tuple]):
        for signal, slot in bucket:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):  # 已断开 / 对象已销毁
                pass
        bucket.clear()
