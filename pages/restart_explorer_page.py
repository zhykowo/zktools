"""重启文件资源管理器模块：无界面"假页面"（VirtualPage）。

模块中心点击卡片后，后台执行 taskkill 终止 explorer.exe 并手动重新启动，
通过全局通知页弹出进度提示。
"""

import logging
import subprocess
import threading

from pages.notify_page import VirtualPage, notify
from resources.svgs import restart_icon

logger = logging.getLogger(__name__)


class RestartExplorerPage(VirtualPage):
    """Restart File Explorer — module center card triggers a restart"""

    PAGE_NAME = "restart_explorer"
    MODULE_NAME = "ReExplorer"
    MODULE_ICON = restart_icon

    def on_module_center_clicked(self):
        """Card click: restart explorer.exe in background"""
        notify("Restarting Explorer…", icon=restart_icon, duration=0)
        threading.Thread(target=self._restart_explorer, daemon=True).start()

    def _restart_explorer(self):
        try:
            # Force-kill explorer.exe
            subprocess.run(
                ["taskkill", "/f", "/im", "explorer.exe"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Manually restart explorer.exe
            subprocess.Popen(
                "explorer.exe",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            notify("Explorer restarted", icon=restart_icon, duration=3000)
        except Exception as e:
            logger.error(f"Restart Explorer failed: {e}")
            notify("Restart failed", icon=restart_icon, duration=3000)
