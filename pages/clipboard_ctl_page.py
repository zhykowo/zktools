"""剪贴板模块：无界面"假页面"（VirtualPage）。

剪贴板变化时经全局通知页弹出 "Copied!" 提醒；
仅当当前处于 home/通知页时提醒（only_when_idle），不打断使用中的页面。
连接依赖 clipboard_monitor 已 init()（main.py 启动顺序已保证）。
"""
import utils.clipboard_monitor as clipboard_monitor

from pages.notify_page import VirtualPage, notify

from resources.svgs import clipboard_icon


class ClipboardCtlPage(VirtualPage):
    """剪贴板变化通知的模块入口：无界面，不显示在模块中心"""

    PAGE_NAME = "clipboard"

    def __init__(self, parent=None):
        super().__init__(parent)
        clipboard_monitor.get().cbChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self, _text: str):
        notify("Copied!", icon=clipboard_icon, duration=1500, only_when_idle=True)
