"""逻辑层单测：不构造任何 QWidget、不启动 QApplication、不联网。

证明 TranslatorScript 可以完全脱离界面独立运行与断言。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, Signal

from modules.translator.script import SyncTranslationRunner, TranslatorScript
from resources.constants import CONFIG


class FakeTranslator:
    """不联网的翻译器替身：记录入参并返回可预测结果"""

    def __init__(self):
        self.calls: list[tuple] = []

    def translate_text(self, text, server, from_lang, to_lang):
        self.calls.append((text, server, from_lang, to_lang))
        return f"[{server}]{from_lang}->{to_lang}:{text}"


class StalledRunner(QObject):
    """永不自动完成的执行器替身：用于验证取消逻辑"""

    finished = Signal(object)

    def __init__(self, translator, text, server, from_lang, to_lang, parent=None):
        super().__init__(parent)
        self.cancelled = False
        self.cleaned = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def cleanup(self):
        self.cleaned = True


class Recorder:
    """信号记录器：当作槽直接 connect"""

    def __init__(self):
        self.args: list[tuple] = []

    def __call__(self, *args):
        self.args.append(args)

    @property
    def last(self):
        return self.args[-1] if self.args else None


def make_script(runner_factory=SyncTranslationRunner):
    translator = FakeTranslator()
    script = TranslatorScript(translator=translator, runner_factory=runner_factory)
    return script, translator


class TranslatorScriptStateTest(unittest.TestCase):
    def test_default_state_comes_from_logic_layer(self):
        script, _ = make_script()
        # 语种 / 服务默认值由逻辑层从配置读出，界面不再自己读配置
        self.assertIn(script.from_lang, script.SUPPORTED_LANGUAGES)
        self.assertIn(script.to_lang, script.SUPPORTED_LANGUAGES)
        self.assertIn(script.server, script.SUPPORTED_SERVERS)
        self.assertEqual(script.server_display, script.server_items()[script.SUPPORTED_SERVERS.index(script.server)])

    def test_server_selection_maps_display_name_to_id(self):
        script, _ = make_script()
        items = script.server_items()
        changed = Recorder()
        script.server_changed.connect(changed)

        script.set_server(items[-1])  # 最后一个 AI 服务（显示名取自配置 name）
        self.assertEqual(script.server, "AI2")
        self.assertEqual(script.server_display, items[-1])
        self.assertEqual(changed.last, (items[-1],))

        # 未知显示名不应改变状态
        script.set_server("不存在的服务")
        self.assertEqual(script.server, "AI2")
        self.assertEqual(len(changed.args), 1)

    def test_swap_languages_falls_back_to_english(self):
        script, _ = make_script()
        script.set_from_lang("Auto")
        script.set_to_lang("Chinese")
        script.swap_languages()
        self.assertEqual(script.from_lang, "Chinese")
        self.assertEqual(script.to_lang, "English")  # 源为 Auto 时目标不能是 Auto

        script.swap_languages()
        self.assertEqual(script.from_lang, "English")
        self.assertEqual(script.to_lang, "Chinese")

    def test_emit_state_broadcasts_full_state(self):
        script, _ = make_script()
        seen = {name: Recorder() for name in ("input", "result", "from", "to", "server", "busy")}
        script.input_text_changed.connect(seen["input"])
        script.result_text_changed.connect(seen["result"])
        script.from_lang_changed.connect(seen["from"])
        script.to_lang_changed.connect(seen["to"])
        script.server_changed.connect(seen["server"])
        script.translating_changed.connect(seen["busy"])

        script.emit_state()
        self.assertEqual(seen["from"].last, (script.from_lang,))
        self.assertEqual(seen["to"].last, (script.to_lang,))
        self.assertEqual(seen["server"].last, (script.server_display,))
        self.assertEqual(seen["busy"].last, (False,))


class TranslatorScriptFlowTest(unittest.TestCase):
    def test_translation_flow(self):
        script, translator = make_script()
        result = Recorder()
        panel = Recorder()
        busy = Recorder()
        script.result_text_changed.connect(result)
        script.result_panel_requested.connect(panel)
        script.translating_changed.connect(busy)

        script.set_input_text("hello")
        script.request_translation()

        expect = f"[{script.server}]{script.from_lang}->{script.to_lang}:hello"
        self.assertEqual(script.result_text, expect)
        self.assertEqual(result.last, (expect,))
        self.assertEqual(panel.last, (True,))
        self.assertEqual(busy.args, [(True,), (False,)])
        self.assertEqual(translator.calls[-1][0], "hello")
        self.assertFalse(script.is_translating)

    def test_duplicate_request_ignored_while_busy(self):
        created = []

        def factory(*args, **kwargs):
            runner = StalledRunner(*args, **kwargs)
            created.append(runner)
            return runner

        script, _ = make_script(factory)
        script.set_input_text("hello")
        script.request_translation()
        script.request_translation()  # 在途任务未结束，重复点击应被忽略
        self.assertEqual(len(created), 1)
        self.assertTrue(script.is_translating)

    def test_cancel_discards_late_result(self):
        created = []

        def factory(*args, **kwargs):
            runner = StalledRunner(*args, **kwargs)
            created.append(runner)
            return runner

        script, _ = make_script(factory)
        result = Recorder()
        script.result_text_changed.connect(result)

        script.set_input_text("hello")
        script.request_translation()
        self.assertTrue(script.is_translating)

        script.cancel_translation()
        self.assertFalse(script.is_translating)
        self.assertTrue(created[0].cancelled)
        self.assertTrue(created[0].cleaned)

        # 迟到的结果必须被丢弃
        created[0].finished.emit("late result")
        self.assertEqual(script.result_text, "")
        self.assertEqual(result.args, [])

    def test_reset_clears_everything(self):
        script, _ = make_script()
        script.set_input_text("hello")
        script.request_translation()
        script.reset()
        self.assertEqual(script.input_text, "")
        self.assertEqual(script.result_text, "")
        self.assertFalse(script.is_translating)


class TranslatorScriptOneClickTest(unittest.TestCase):
    def test_one_click_flow(self):
        script, _ = make_script()
        copy = Recorder()
        activate = Recorder()
        focus = Recorder()
        script.copy_shortcut_requested.connect(copy)
        script.activate_requested.connect(activate)
        script.input_focus_requested.connect(focus)

        # 未触发热键时，剪贴板文本应被忽略
        script.on_clipboard_text("ignored")
        self.assertEqual(copy.args, [])
        self.assertEqual(script.input_text, "")

        script.one_click_triggered()
        self.assertEqual(copy.last, ("ctrl+c",))

        script.on_clipboard_text("selected text")
        self.assertEqual(activate.args, [()])
        self.assertEqual(focus.args, [()])
        self.assertEqual(script.input_text, "selected text")
        self.assertFalse(script.is_translating)  # 同步执行器：翻译已即时完成
        self.assertIn("selected text", script.result_text)

    def test_empty_clipboard_aborts(self):
        script, _ = make_script()
        script.one_click_triggered()
        script.on_clipboard_text("")
        self.assertEqual(script.input_text, "")

        # 等待态已被消费，后续剪贴板变化不再触发
        script.on_clipboard_text("later")
        self.assertEqual(script.input_text, "")

    def test_submit_external_text_resets_to_defaults(self):
        script, _ = make_script()
        script.set_from_lang("Japanese")
        script.set_to_lang("Korean")
        script.set_server("Google")

        script.submit_external_text("ocr result")
        self.assertEqual(script.input_text, "ocr result")
        # 外部文本进入时复位为配置默认值
        self.assertEqual(script.from_lang, CONFIG["translator"]["default_from_lang"])
        self.assertEqual(script.to_lang, CONFIG["translator"]["default_to_lang"])
        self.assertEqual(script.server, CONFIG["translator"]["default_server"])
        self.assertIn("ocr result", script.result_text)


if __name__ == "__main__":
    unittest.main()
