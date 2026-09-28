"""调度层单测：验证 view ↔ script 的转接是否成立。

重点验证两件事：
1. 界面操作能驱动逻辑、逻辑状态能回灌界面；
2. detach_view() 之后（甚至界面对象被彻底释放）逻辑层照常运行。
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from modules.translator.controller import TranslatorController
from modules.translator.script import SyncTranslationRunner, TranslatorScript
from utils import clipboard_monitor

_app = QApplication.instance() or QApplication([])
clipboard_monitor.init()  # 让 controller 能接上剪贴板入口（与 main.py 启动顺序一致）


class FakeTranslator:
    def __init__(self):
        self.calls: list[tuple] = []

    def translate_text(self, text, server, from_lang, to_lang):
        self.calls.append((text, server, from_lang, to_lang))
        return f"[{server}]{from_lang}->{to_lang}:{text}"


class StalledRunner(QObject):
    """永不自动完成的执行器替身：让"翻译中"状态停在那里，便于验证取消"""

    finished = Signal(object)

    def __init__(self, translator, text, server, from_lang, to_lang, parent=None):
        super().__init__(parent)

    def start(self):
        pass

    def cancel(self):
        pass

    def cleanup(self):
        pass


class TranslatorControllerTest(unittest.TestCase):
    def build(self):
        translator = FakeTranslator()
        script = TranslatorScript(translator=translator, runner_factory=SyncTranslationRunner)
        controller = TranslatorController(script=script, enable_hotkey=False)
        return controller, script, translator

    def tearDown(self):
        QApplication.processEvents()

    def test_initial_state_pushed_to_view(self):
        controller, script, _ = self.build()
        view = controller.page
        self.assertEqual(view.origin_lang.text(), script.from_lang)
        self.assertEqual(view.target_lang.text(), script.to_lang)
        self.assertEqual(view.translation_server_btn.text(), script.server_display)
        controller.shutdown()

    def test_user_input_reaches_script(self):
        controller, script, _ = self.build()
        view = controller.page
        view.input_text.setPlainText("hello")
        self.assertEqual(script.input_text, "hello")
        controller.shutdown()

    def test_translate_click_runs_and_renders(self):
        controller, script, translator = self.build()
        view = controller.page
        view.input_text.setPlainText("hello")
        view.translation_server_btn.click()

        self.assertEqual(len(translator.calls), 1)
        self.assertEqual(view.result_text.toPlainText(), script.result_text)
        self.assertFalse(script.is_translating)
        self.assertFalse(view.translation_server_btn.isHidden())
        controller.shutdown()

    def test_swap_click_updates_both_buttons(self):
        controller, script, _ = self.build()
        view = controller.page
        old_from, old_to = script.from_lang, script.to_lang
        view.swap_btn.clicked.emit(False)
        self.assertEqual(script.from_lang, old_to)
        self.assertEqual(view.origin_lang.text(), script.from_lang)
        self.assertEqual(view.target_lang.text(), script.to_lang)
        controller.shutdown()

    def test_cancel_click_stops_translation(self):
        translator = FakeTranslator()
        script = TranslatorScript(translator=translator, runner_factory=StalledRunner)
        controller = TranslatorController(script=script, enable_hotkey=False)
        view = controller.page

        view.input_text.setPlainText("hello")
        view.translation_server_btn.click()
        self.assertTrue(script.is_translating)
        self.assertTrue(view.translation_server_btn.isHidden())  # 翻译中：翻译按钮让位
        self.assertFalse(view.cancel_btn.isHidden())

        view.cancel_btn.click()
        self.assertFalse(script.is_translating)
        self.assertFalse(view.translation_server_btn.isHidden())
        self.assertTrue(view.cancel_btn.isHidden())
        controller.shutdown()

    def test_server_grid_selection_reaches_script(self):
        controller, script, _ = self.build()
        view = controller.page
        items = script.server_items()

        view.server_requested.emit()
        self.assertTrue(view.selection_grid.is_expanded)

        buttons = view.selection_grid.button_group.buttons()
        buttons[-1].click()  # 最后一个 AI 服务
        self.assertEqual(script.server, "AI2")
        self.assertEqual(view.translation_server_btn.text(), items[-1])
        controller.shutdown()

    def test_language_grid_selection_reaches_script(self):
        controller, script, _ = self.build()
        view = controller.page
        view.origin_lang_requested.connect(lambda: None)  # controller 已接管，重复连接仅用于确认信号存在
        view.origin_lang.click()
        buttons = view.selection_grid.button_group.buttons()
        buttons[1].click()  # English
        self.assertEqual(script.from_lang, "English")
        self.assertEqual(view.origin_lang.text(), "English")
        controller.shutdown()

    # ---------- 关键诉求：释放界面后逻辑层照常 ----------
    def test_logic_survives_view_release(self):
        controller, script, translator = self.build()
        view = controller.page

        detached = controller.detach_view()
        self.assertIs(detached, view)
        self.assertIsNone(controller.view)

        # 界面还在，但已与逻辑层断连：逻辑变化不再回灌界面
        before = view.result_text.toPlainText()
        script.set_input_text("after detach")
        script.request_translation()
        self.assertEqual(view.result_text.toPlainText(), before)
        self.assertIn("after detach", script.result_text)

        # 彻底释放 QWidget 对象，逻辑层仍可继续工作
        view.deleteLater()
        QApplication.processEvents()
        script.set_input_text("after delete")
        script.request_translation()
        self.assertIn("after delete", script.result_text)
        self.assertEqual(translator.calls[-1][0], "after delete")

        controller.shutdown()


if __name__ == "__main__":
    unittest.main()
