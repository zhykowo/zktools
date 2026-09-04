"""可复用的按钮选择网格组件

将按钮网格布局封装为独立组件，支持：
- 自定义列数、间距、按钮高度
- 指定当前选中项（高亮）、其余灰色
- 点击回调
- 可动画化的高度属性（anim_height），供 WidgetAnimator 使用
"""

from functools import partial

from PySide6.QtCore import Property, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QWidget

from core.colors import NEUTRAL_2
from widgets.core_button import CoreButton


class SelectionGrid(QWidget):
    """通用平铺选择网格

    用法示例::

        grid = SelectionGrid(parent)
        grid.configure(cols=3, item_height=36, spacing=8)
        grid.populate(items, current_value, on_select)
        height = grid.calculate_height(len(items))

    点击网格项后发射 ``item_selected`` 信号，调用者可按需连接额外操作
    （如收起网格），网格本身不绑定收起行为。
    """

    item_selected = Signal(str)  # 点击项时发射，携带选中文本

    def __init__(self, parent=None):
        super().__init__(parent)

        self._idle_bg = NEUTRAL_2
        self._cols = 3
        self._item_height = 36
        self._spacing = 8

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(self._spacing)

        self.setMinimumHeight(0)
        self.setMaximumHeight(0)

    # ==================== 可动画化的高度属性 ====================

    def _get_anim_height(self):
        return self.height()

    def _set_anim_height(self, h):
        self.setFixedHeight(h)

    anim_height = Property(int, _get_anim_height, _set_anim_height)

    # ==================== 公共接口 ====================

    def configure(self, cols=None, item_height=None, spacing=None, idle_bg=None):
        """配置网格参数（初始化时调用，不要在 populate 后调用）"""
        if cols is not None:
            self._cols = cols
        if item_height is not None:
            self._item_height = item_height
        if spacing is not None:
            self._spacing = spacing
            self.grid_layout.setSpacing(self._spacing)
        if idle_bg is not None:
            self._idle_bg = idle_bg

    def populate(self, items: list[str], current_value: str, on_select_callback):
        """填充按钮并更新网格

        Args:
            items: 所有选项文本列表
            current_value: 当前选中值（高亮显示），其余灰色
            on_select_callback: 选中回调，接收选中文本
        """
        self._clear()

        for idx, text in enumerate(items):
            btn = CoreButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if text != current_value:
                btn.setBgColor(self._idle_bg)
            btn.clicked.connect(
                partial(self._on_item_click, text, on_select_callback)
            )
            row, col = divmod(idx, self._cols)
            self.grid_layout.addWidget(btn, row, col)

    def calculate_height(self, item_count: int) -> int:
        """根据项数计算网格所需高度"""
        cols = self._cols
        rows = (item_count + cols - 1) // cols
        return rows * self._item_height + (rows - 1) * self._spacing

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def item_height(self) -> int:
        return self._item_height

    # ==================== 内部方法 ====================

    def _clear(self):
        """清空所有按钮"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _on_item_click(self, selected_text: str, callback):
        """点击项处理：更新按钮高亮后调用上层回调"""
        # 遍历网格中所有按钮，将选中的恢复为 accent 高亮，其余置灰
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item is not None:
                btn = item.widget()
                if isinstance(btn, CoreButton):
                    if btn.text() == selected_text:
                        btn.resetBgColor()
                    else:
                        btn.setBgColor(self._idle_bg)
        callback(selected_text)
        self.item_selected.emit(selected_text)