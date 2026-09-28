"""界面层单测：只构造 QWidget，完全不 import TranslatorScript。

证明 TranslatorView 可以脱离逻辑层独立运行与断言：
喂信号 → 断言控件；调渲染槽 → 断言界面。
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.translator.view import TranslatorView

_app = QApplication.instance() or QApplication([])


class Recorder:
    def __init__(self):
        self.args: list[tuple] = []

    def __call__(self, *args):
        self.args.append(args)

    @property
    def last(self):
        return self.args[-1] if self.args else None


class TranslatorViewTest(unittest.TestCase):
    def setUp(self):
        self.view = TranslatorView()

    def tearDown(self):
        self.view.deleteLater()
        QApplication.processEvents()

    # ---------------- 用户意图采集 ----------------
    def test_input_editing_emits_signal(self):
        got = Recorder()
        self.view.input_changed.connect(got)
        self.view.input_text.setPlainText("hello")
        self.assertEqual(got.last, ("hello",))

    def test_button_clicks_emit_signals(self):
        cases = {
            "translate": (self.view.translate_clicked, self.view.translation_server_btn),
            "cancel": (self.view.cancel_clicked, self.view.cancel_btn),
            "swap": (self.view.swap_clicked, None),  # SvgButton 非 QAbstractButton，单独触发
        }
        for name, (signal, button) in cases.items():
            with self.subTest(name):
                got = Recorder()
                signal.connect(got)
                if button is not None:
                    button.click()
                else:
                    self.view.swap_btn.clicked.emit(False)
                self.assertEqual(got.args, [()])

    def test_language_button_click_requests_grid(self):
        got = Recorder()
        self.view.origin_lang_requested.connect(got)
        self.view.origin_lang.click()
        self.assertEqual(got.args, [()])

    # ---------------- 网格交互（纯界面行为，不需要逻辑层）----------------
    def test_grid_selection_updates_button_and_emits(self):
        got = Recorder()
        self.view.origin_lang_selected.connect(got)
        # 模拟 controller：收到请求后把可选项喂回界面
        self.view.origin_lang_requested.connect(lambda: self.view.open_origin_grid(["Auto", "English", "Chinese"], "Auto"))

        self.view.origin_lang.click()
        self.assertTrue(self.view.selection_grid.is_expanded)

        buttons = self.view.selection_grid.button_group.buttons()
        self.assertEqual([b.text() for b in buttons], ["Auto", "English", "Chinese"])
        self.assertTrue(buttons[0].isChecked())  # 当前值预选中

        buttons[1].click()
        self.assertEqual(got.last, ("English",))
        self.assertEqual(self.view.origin_lang.text(), "English")

    def test_opening_grid_collapses_result_panel(self):
        self.view.set_result_expanded(True)
        self.view.origin_lang_requested.connect(lambda: self.view.open_origin_grid(["Auto", "English"], "Auto"))
        self.view.origin_lang.click()
        self.assertFalse(self.view._result_expanded)

    # ---------------- 渲染槽 ----------------
    def test_render_slots(self):
        self.view.set_input_text("abc")
        self.view.set_result_text("译文")
        self.view.set_from_lang("Japanese")
        self.view.set_to_lang("Korean")
        self.view.set_server_display("DeepSeek")
        self.assertEqual(self.view.input_text.toPlainText(), "abc")
        self.assertEqual(self.view.result_text.toPlainText(), "译文")
        self.assertEqual(self.view.origin_lang.text(), "Japanese")
        self.assertEqual(self.view.target_lang.text(), "Korean")
        self.assertEqual(self.view.translation_server_btn.text(), "DeepSeek")

    def test_programmatic_input_write_does_not_echo(self):
        got = Recorder()
        self.view.input_changed.connect(got)
        self.view.set_input_text("来自逻辑层的回填")
        self.assertEqual(got.args, [])  # 回声必须被阻断，否则逻辑层会自我循环

    def test_translating_state_swaps_buttons(self):
        self.view.set_translating(True)
        self.assertFalse(self.view.cancel_btn.isHidden())
        self.assertTrue(self.view.translation_server_btn.isHidden())
        self.view.set_translating(False)
        self.assertTrue(self.view.cancel_btn.isHidden())
        self.assertFalse(self.view.translation_server_btn.isHidden())

    # ---------------- 生命周期 ----------------
    def test_clear_data_emits_and_resets(self):
        got = Recorder()
        self.view.clear_requested.connect(got)
        self.view.input_text.setPlainText("x")
        self.view.clear_data()
        self.assertEqual(got.args, [()])
        self.assertEqual(self.view.input_text.toPlainText(), "")

    def test_back_closes_grid_first(self):
        got = Recorder()
        self.view.back_requested.connect(got)
        self.view.origin_lang_requested.connect(lambda: self.view.open_origin_grid(["Auto", "English"], "Auto"))

        self.view.origin_lang.click()
        self.view.on_back_clicked()  # 网格展开时：只收起网格
        self.assertEqual(got.args, [])
        self.assertFalse(self.view.selection_grid.is_expanded)

        self.view.on_back_clicked()  # 网格已收起：请求退出页面
        self.assertEqual(got.args, [()])


if __name__ == "__main__":
    unittest.main()
