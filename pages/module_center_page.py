from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from core.colors import NEUTRAL_5
from core.page_router import page_router
from pages.base_page import BasePage
from pages.notify_page import VirtualPage
from resources.svgs import square_icon
from widgets.svg_button import SvgButton


class ModuleCard(QWidget):
    """单个模块卡片：上图下字组件"""

    def __init__(self, name: str = "", icon_data=square_icon, parent=None):
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
    """模块中心：纯展示页。

    卡片内容不在此硬编码，只读取各页面的 module_name：
    - 进入页面时（on_show）全量刷新卡片；
    - 页面自身名称变化时（module_name_changed 信号）实时更新对应卡片。
    点击卡片统一跳转到对应页面，无任何模块特殊逻辑。
    """

    PAGE_NAME = "module_center"
    TITLE = "Module Center"

    GRID_COLS = 3

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        main_layout = self.set_main_layout("v")
        assert main_layout is not None

        # 2. 模块网格（按注册页面的 module_name 动态生成）
        grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setHorizontalSpacing(12)
        self.grid_layout.setVerticalSpacing(12)

        self._cards = {}  # page_name -> ModuleCard
        self._signals_connected = False

        main_layout.addWidget(grid_widget)
        main_layout.addStretch()

    def on_show(self):
        """进入页面时：幂等连接各页面的名称变化信号，并按最新名称全量刷新"""
        self._connect_name_signals()
        self.refresh()

    def _connect_name_signals(self):
        """订阅所有已注册页面的 module_name_changed（仅一次）"""
        if self._signals_connected:
            return
        self._signals_connected = True
        for page in page_router.pages.values():
            page.module_name_changed.connect(self._on_module_name_changed)

    def refresh(self):
        """重建卡片网格：只读取各页面的 module_name / module_icon，空名页面不显示"""
        # 清空旧卡片
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._cards.clear()

        for index, (page_name, page) in enumerate(page_router.pages.items()):
            if not page.module_name:
                continue
            card = ModuleCard(parent=self)
            # 点击行为由页面自身决定（BasePage.on_module_center_clicked），
            # 本页不感知任何模块特殊性
            card.icon_btn.clicked.connect(
                lambda _=None, p=page: p.on_module_center_clicked()
            )
            row, col = divmod(index, self.GRID_COLS)
            self.grid_layout.addWidget(card, row, col)
            self._cards[page_name] = card
            self._apply_module_center_info(card, page)

    @Slot()
    def _on_module_name_changed(self):
        """某页面模块中心信息（名称/图标）变化：实时更新对应卡片"""
        page = self.sender()
        if page is None:
            return
        page_name = getattr(page, "page_name", None)
        if page_name is None:
            return
        card = self._cards.get(page_name)
        if card is None:
            # 变化来自尚未展示的页面（如首次出现）：整体重建一次
            self.refresh()
            return
        if isinstance(page, (BasePage, VirtualPage)):
            self._apply_module_center_info(card, page)

    @staticmethod
    def _apply_module_center_info(
        card: ModuleCard, page: BasePage | VirtualPage
    ) -> None:
        """把页面的 module_center 名称与图标应用到卡片（构建与信号刷新共用同一逻辑）"""
        card.label.setText(page.module_name or "")
        icon = page.module_icon
        if icon:
            card.icon_btn.set_svg(icon)
