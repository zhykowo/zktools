from pages.base_page import BasePage

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QWidget
)
from PySide6.QtGui import QPalette, QColor

from widgets.svg_button import SvgButton

from core.page_controller import page_signals

from resources.svgs import arrow_left_icon, square_icon


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
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#CCCCCC"))
        self.label.setPalette(palette)

        layout.addWidget(self.icon_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)


class ModuleCenterPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        # 主布局：紧凑外边距，为网格留出充分空间
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(8)

        # 1. 顶部栏（返回按钮 + 页面标题）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        back_btn = SvgButton(self, icon_size=20, svg_data=arrow_left_icon)
        back_btn.clicked.connect(lambda: page_signals.exit_self())

        title_label = QLabel("模块中心", self)
        title_font = title_label.font()
        title_font.setPixelSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)

        title_palette = title_label.palette()
        title_palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        title_label.setPalette(title_palette)

        header_layout.addWidget(back_btn)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

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
        page_signals.immediate_switch(module_name)

    # def mousePressEvent(self, event):
    #     widget = self.childAt(event.pos())
    #     print(f"当前点击位置的实际顶层组件为: {widget}")
    #     super().mousePressEvent(event)