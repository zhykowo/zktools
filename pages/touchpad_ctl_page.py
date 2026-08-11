"""
触摸板控制页:展示触摸板开关状态,并通过全局热键在后台切换触摸板设备。

线程模型:
- 热键回调运行在 hotkey_manager 的工作线程,只做状态裁决并发射信号,绝不触碰 UI;
- 阻塞的开关操作(run_switch_touchpad)放在独立工作线程执行,避免卡住热键监听线程;
- 所有 UI 更新都通过信号回到主线程完成。
"""
import threading
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QLabel

from core.page_router import page_router
from core.hotkey_manager import hotkey_manager

from pages.base_page import BasePage

from utils.switch_touchpad.switch_touchpad import run_switch_touchpad

from resources.constants import CONFIG


class TouchpadState(Enum):
    """触摸板开关状态机"""

    DISABLED = "Disabled"
    ENABLED = "Enabled"
    DISABLING = "Disabling"
    ENABLING = "Enabling"

    @property
    def is_transitioning(self) -> bool:
        """是否处于切换中的中间态(此时忽略新的切换请求)"""
        return self in (TouchpadState.DISABLING, TouchpadState.ENABLING)


class TouchpadController(QObject):
    """触摸板开关控制器:线程安全的状态裁决 + 后台执行开关操作"""

    # 状态变化信号(在主线程消费,携带 TouchpadState)
    state_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = TouchpadState.DISABLED
        self._lock = threading.Lock()  # 保护 _state 的跨线程访问

    @property
    def state(self) -> TouchpadState:
        with self._lock:
            return self._state

    def request_switch(self):
        """热键回调入口(工作线程)。非过渡态时发起一次切换。"""
        with self._lock:
            if self._state.is_transitioning:
                return
            previous = self._state
            if previous == TouchpadState.ENABLED:
                intermediate, final, enable = (
                    TouchpadState.DISABLING,
                    TouchpadState.DISABLED,
                    False,
                )
            else:
                intermediate, final, enable = (
                    TouchpadState.ENABLING,
                    TouchpadState.ENABLED,
                    True,
                )
            self._state = intermediate

        # 通知主线程:展示中间态并切到本页
        self.state_changed.emit(intermediate)

        # 阻塞操作放入工作线程,热键监听线程立即返回
        threading.Thread(
            target=self._perform_switch,
            args=(enable, final, previous),
            daemon=True,
            name="touchpad-switch",
        ).start()

    def _perform_switch(self, enable: bool, final: TouchpadState, previous: TouchpadState):
        """工作线程:执行开关操作,完成后把结果送回主线程。"""
        try:
            run_switch_touchpad(enable=enable)
        except Exception as exc:  # 防御:设备枚举/提权失败不应导致崩溃
            print(f"[TouchpadController] 切换失败: {exc}")
            final = previous  # 恢复为操作前的状态

        with self._lock:
            self._state = final
        self.state_changed.emit(final)


class TouchpadCtlPage(BasePage):
    """触摸板控制页:展示开关状态,热键在后台驱动开关"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (250, 50)
        layout = self.set_main_layout("h")

        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.controller = TouchpadController(self)
        self.controller.state_changed.connect(self._on_state_changed)

        # 切换完成后短暂停留再自动退出(可重置,避免定时器堆叠)
        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self._quit)

        self._register_hotkeys()

    def on_show(self):
        """进入页面时刷新当前状态(仅展示,不安排自动退出)"""
        self._render_state(self.controller.state)

    def _register_hotkeys(self):
        hotkey_manager.start()
        test_ok = hotkey_manager.register(
            CONFIG["touchpad_ctl"]["hotkeys"]["test"], self._on_test_hotkey
        )
        switch_ok = hotkey_manager.register(
            CONFIG["touchpad_ctl"]["hotkeys"]["switch"], self.controller.request_switch
        )
        if not test_ok or not switch_ok:
            print("[TouchpadCtlPage] 警告：部分触控板控制热键注册失败，相关快捷键将不可用")

    def _on_test_hotkey(self):
        """测试热键回调(工作线程):仅打印,不触碰 UI"""
        print("\n💥 触发了测试动作 (Ctrl + Alt + A)")

    # 主线程槽:热键切换流程的 UI 驱动
    @Slot(object)
    def _on_state_changed(self, state: TouchpadState):
        if state.is_transitioning:
            # 开始切换:立即切到本页展示中间态(如 "Disabling")
            page_router.immediate_switch("switch_touchpad")
        self._render_state(state)

        if not state.is_transitioning:
            # 切换完成:展示最终状态,停留 3 秒后自动退出
            self._exit_timer.start(3000)

    def _render_state(self, state: TouchpadState):
        self.label.setText(f"TouchPad {state.value}")

    def _quit(self):
        page_router.exit_self(self.page_name)
