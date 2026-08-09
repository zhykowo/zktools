from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QLabel

from core.page_controller import page_signals
from core.hotkey_manager import hotkey_manager

from pages.base_page import BasePage

from utils.switch_touchpad.switch_touchpad import run_switch_touchpad

from resources.constants import CONFIG

class TouchpadCtlPage(BasePage):
    # 1. 明确定义一个 Qt 信号，用于将子线程的触发通知安全送回主线程
    trigger_switch_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (250, 50)
        layout = self.set_main_layout('h')
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.hotkey_manager = None
        self.current_struct = "Disabled"
        # 将此信号绑定到主线程安全的执行函数上
        self.trigger_switch_signal.connect(self.on_hotkey_triggered)

        self.start()

    def action_a(self):
        print("\n💥 触发了测试动作 (Ctrl + Alt + A)")

    def quit_msg(self):
        page_signals.exit_self()

    def update_text(self):
        if self.current_struct:
            self.label.setText(f"TouchPad {self.current_struct}")
            page_signals.immediate_switch("switch_touchpad")

    def switch_action(self):
        if self.current_struct == "Disabling" or self.current_struct == "Enabling":
            return

        # 发射信号，通知主线程
        self.trigger_switch_signal.emit()

        if self.current_struct == "Enabled":
            self.current_struct = "Disabling"
            run_switch_touchpad(enable=False)
            self.current_struct = "Disabled"

        elif self.current_struct == "Disabled":
            self.current_struct = "Enabling"
            run_switch_touchpad(enable=True)
            self.current_struct = "Enabled"

        self.quit_msg()
        self.trigger_switch_signal.emit()

    # 4. 这个槽函数由信号触发，会自动在【主线程】中执行
    @Slot()
    def on_hotkey_triggered(self):
        # 此时已经安全回到主线程，可以放心操作 UI 和 QTimer
        self.update_text()
        QTimer.singleShot(3000, self.quit_msg) 

    def start(self):
        hotkey_manager.register(CONFIG['touchpad_ctl']['hotkeys']['test'], self.action_a)
        hotkey_manager.register(CONFIG['touchpad_ctl']['hotkeys']['switch'], self.switch_action)
        hotkey_manager.start()
