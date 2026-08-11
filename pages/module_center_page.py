from pages.base_page import BasePage

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QGridLayout, QLabel, QWidget
)
from PySide6.QtGui import QPalette

from widgets.svg_button import SvgButton

from core.page_router import page_router

from resources.svgs import square_icon
from resources.colors import NEUTRAL_5


class ModuleCard(QWidget):
    """单个模块卡片：上图下字组件"""
    def __init__(self, name: str, icon_data=square_icon, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 小图标 (22x22 黄金比例大小)
        self.icon_btn = SvgButton(self, icon_size=22, svg_data=icon_data)
        
        # 模块名称
        self.label = QLabel(name, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        font = self.label.font()
        font.setPixelSize(11)
        self.label.setFont(font)

        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, NEUTRAL_5)
        self.label.setPalette(palette)

        layout.addWidget(self.icon_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

class ModuleCenterPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        main_layout = self.set_main_layout(d='v', title='Module Center')

        # 2. 模块网格 (3列 x 2行，共6个核心模块)
        grid_widget = QWidget(self)
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(12)

        modules = [
            ("translator", self._on_module_click),
            ("占位符", self._on_module_click),
            ("占位符", self._on_module_click),
            ("占位符", self._on_module_click),
            ("占位符",   self._on_module_click),
            ("占位符", self._on_module_click),
        ]

        for index, (mod_name, callback) in enumerate(modules):
            row, col = divmod(index, 3)
            card = ModuleCard(name=mod_name, icon_data=square_icon, parent=self)
            card.icon_btn.clicked.connect(lambda _, name=mod_name: callback(name))
            grid_layout.addWidget(card, row, col)

        main_layout.addWidget(grid_widget)
        main_layout.addStretch()

    def _on_module_click(self, module_name: str):
        print(f"点击模块: {module_name}")
        page_router.immediate_switch(module_name)

    # def mousePressEvent(self, event):
    #     widget = self.childAt(event.pos())
    #     print(f"当前点击位置的实际顶层组件为: {widget}")
    #     super().mousePressEvent(event)