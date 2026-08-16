"""
触摸板控制模块:全局热键在后台切换触摸板设备,状态提醒统一走全局通知页。

线程模型:
- 热键回调运行在 hotkey_manager 的 Qt 主线程分发中,只做状态裁决并发射信号;
- 阻塞的开关操作(run_switch_touchpad)放在独立工作线程执行,避免卡住事件循环;
- 所有 UI 更新都通过信号回到主线程完成。

页面职责:
- 本页不再有独立展示界面,状态展示(切换中/最终结果)统一由
  pages.notify_page.notify() 弹出通知完成;
- 仍作为模块入口注册在 main.py,承担热键注册与模块中心卡片:
  module_name 属性按状态动态提供卡片文本("TchPad Off"/"TchPad On"),
  状态变化时发出 module_name_changed 信号,由 module_center_page 订阅刷新。
"""
import threading
from enum import Enum

from PySide6.QtCore import QObject, Signal, Slot

from core.hotkey_manager import hotkey_manager

from pages.base_page import BasePage
from pages.notify_page import notify

from utils.switch_touchpad import run_switch_touchpad, get_touchpad_status

from resources.svgs import touchpad_icon
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
        self._lock = threading.Lock()  # 保护 _state 的跨线程访问
        # 启动时读取系统真实状态,避免初始显示与实际情况不一致
        # (touchpad_ctl_page 与 module_center_page 均以 controller.state 初始化显示)
        self._state = self._read_initial_state()

    @staticmethod
    def _read_initial_state() -> TouchpadState:
        """启动时查询触摸板真实状态;查询失败时回退为禁用(与旧默认行为一致)"""
        enabled = get_touchpad_status()
        if enabled is None:
            print("[TouchpadController] 读取触摸板状态失败,按禁用状态初始化")
            return TouchpadState.DISABLED
        return TouchpadState.ENABLED if enabled else TouchpadState.DISABLED

    @property
    def state(self) -> TouchpadState:
        with self._lock:
            return self._state

    def request_switch(self):
        """热键回调入口(主线程分发)。非过渡态时发起一次切换。"""
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

        # 通知主线程:弹出"切换中"常驻通知
        self.state_changed.emit(intermediate)

        # 阻塞操作放入工作线程,热键分发立即返回
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
    """触摸板控制模块入口:无独立展示界面,仅承担热键注册与模块中心卡片。

    状态展示统一由全局通知页完成:切换中常驻展示(duration=0),
    完成态覆盖它并在 3 秒后自动退出。模块中心显示名由 module_name
    属性按状态动态提供（"TchPad Off"/"TchPad On"），状态变化时发出
    module_name_changed 信号，module_center_page 据此实时刷新。
    """

    PAGE_NAME = "switch_touchpad"
    TITLE = "TouchPad"
    MODULE_NAME = "TchPad Off"  # 兜底；实际通过 module_name 属性动态返回
    MODULE_ICON = touchpad_icon

    def __init__(self, parent=None):
        super().__init__(parent)

        # 使用模块级共享控制器:module_center_page 也订阅它的状态变化
        self.controller = touchpad_controller
        self.controller.state_changed.connect(self._on_state_changed)

        self._register_hotkeys()

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
        """测试热键回调:仅打印,不触碰 UI"""
        print("\n💥 触发了测试动作 (Ctrl + Alt + A)")

    @property
    def module_name(self) -> str:
        """模块中心显示名：按当前触摸板状态动态返回"""
        return self._module_center_text(self.controller.state)

    def on_module_center_clicked(self):
        """模块中心卡片点击：直接触发一次触摸板切换（与全局热键行为一致），
        中间态/完成态的通知弹出与自动退出由 controller 统一驱动"""
        self.controller.request_switch()

    @staticmethod
    def _module_center_text(state: TouchpadState) -> str:
        """触摸板状态 → 模块中心卡片文本：关闭显示 TchPad Off，开启显示 TchPad On"""
        if state in (TouchpadState.DISABLED, TouchpadState.ENABLING):
            return "TchPad Off"
        if state in (TouchpadState.ENABLED, TouchpadState.DISABLING):
            return "TchPad On"
        return "TchPad Off"  # 未知状态兜底

    # 主线程槽:热键切换流程的通知驱动
    @Slot(object)
    def _on_state_changed(self, state: TouchpadState):
        # 切换中:常驻通知(不会被自动退出,只会被完成态覆盖)
        # 切换完成:覆盖"切换中"通知并展示最终状态,3 秒后自动退出
        notify(
            f"TouchPad {state.value}",
            icon=touchpad_icon,
            duration=0 if state.is_transitioning else 3000,
        )
        # 名称随状态变化,通知 module_center_page 实时刷新卡片
        self.module_name_changed.emit()


# 模块级共享控制器单例：触摸板状态由本实例统一裁决与广播，
# touchpad_ctl_page 驱动通知弹出与模块中心的动态名称更新。
touchpad_controller = TouchpadController()
