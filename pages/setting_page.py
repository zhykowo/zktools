# setting_page.py
import logging
import os
import sys
from venv import logger

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel

from pages.base_page import BasePage
from resources.constants import root_dir
from resources.svgs import settings_icon
from widgets.core_button import CoreButton

logger = logging.getLogger(__name__)


class SettingPage(BasePage):
    PAGE_NAME = "setting"
    TITLE = "Setting"
    MODULE_ICON = settings_icon

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = self.set_main_layout("v")
        assert layout is not None

        h_layout = QHBoxLayout()

        open_config_btn = CoreButton(text="Open Config File")
        open_config_btn.clicked.connect(self.open_config)

        restrat_btn = CoreButton(text="Restart", bg_color="danger")
        restrat_btn.clicked.connect(self.restart)

        h_layout.addStretch()
        h_layout.addWidget(open_config_btn)
        h_layout.addStretch()

        layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()

    def open_config(self):
        dev_config = root_dir / "config_dev.json"
        local_config = root_dir / "config.json"

        if dev_config.exists():
            config_path = dev_config
        elif local_config.exists():
            config_path = local_config
        else:
            raise FileNotFoundError(f"未找到配置文件，已尝试路径：\n  {dev_config}\n  {local_config}")
        os.startfile(config_path)

    def restart(self):
        logger.info("正在重启...")
        python = sys.executable
        os.execv(python, [python] + sys.argv)
