"""翻译模块：view / script / controller 三层

对外只需导入 controller（它自己会组装 script 与 view）：

    from modules.translator.controller import TranslatorController

    module = TranslatorController()
    main_window.register_page(TranslatorController.PAGE_NAME, module.page)
"""

from modules.translator.controller import TranslatorController
from modules.translator.script import TranslatorScript
from modules.translator.view import TranslatorView

__all__ = ["TranslatorController", "TranslatorScript", "TranslatorView"]
