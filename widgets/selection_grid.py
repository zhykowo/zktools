"""可复用的按钮选择网格组件

将按钮网格布局封装为独立组件，支持：
- 自定义列数、间距、按钮高度
- 指定当前选中项（高亮）、其余灰色
- 点击回调
- 可动画化的高度属性（anim_height），供 WidgetAnimator 使用
"""

from functools import partial

from PySide6.QtCore import Property, QEasingCurve, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QWidget

from core.colors import NEUTRAL_2
from widgets.core_button import CoreButton
from widgets.widget_animator import WidgetAnimator


class SelectionGrid(QWidget):
    """通用平铺选择网格

    用法示例::

        grid = SelectionGrid(cols=3, item_height=36, spacing=8, parent=parent)
        grid.populate(items, current_value, on_select)
        height = grid.calculate_height(len(items))

    点击网格项后发射 ``item_selected`` 信号，调用者可按需连接额外操作
    （如收起网格），网格本身不绑定收起行为。
    """

    item_selected = Signal(str)  # 点击项时发射，携带选中文本

    def __init__(
        self,
        cols: int = 3,
        item_height: int = 36,
        spacing: int = 8,
        idle_bg=NEUTRAL_2,
        parent=None,
    ):
        super().__init__(parent)

        self._cols = cols
        self._item_height = item_height
        self._spacing = spacing
        self._idle_bg = idle_bg

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(self._spacing)

        self.setMinimumHeight(0)
        self.setMaximumHeight(0)

        self._animator = WidgetAnimator(self)

    # ==================== 可动画化的高度属性 ====================

    def _get_anim_height(self):
        return self.height()

    def _set_anim_height(self, h):
        self.setFixedHeight(h)

    anim_height = Property(int, _get_anim_height, _set_anim_height)

    # ==================== 公共接口 ====================

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
            if text == current_value:
                btn.setBgColor("accent")
            btn.clicked.connect(partial(self._on_item_click, text, on_select_callback))
            row, col = divmod(idx, self._cols)
            self.grid_layout.addWidget(btn, row, col)

    def calculate_height(self, item_count: int) -> int:
        """根据项数计算网格所需高度"""
        cols = self._cols
        rows = (item_count + cols - 1) // cols
        return rows * self._item_height + (rows - 1) * self._spacing

    def expand_to(
        self,
        item_count: int,
        extra_animations=None,
        duration=300,
        easing=None,
        on_finished=None,
    ):
        """展开网格到容纳 item_count 项的高度

        Args:
            item_count: 需要容纳的项数（通过 calculate_height 计算目标高度）
            extra_animations: 与网格并行执行的附加动画，格式为
                [(widget, start_height, end_height), ...]
            duration: 动画时长（毫秒）
            easing: 缓动曲线，默认 OutQuart
            on_finished: 动画完成回调
        """
        target_height = self.calculate_height(item_count)
        current_height = self.height()

        animations = [(self, current_height, target_height)]
        if extra_animations:
            animations.extend(extra_animations)

        self._animator.animate_heights(
            animations,
            duration=duration,
            easing=easing or QEasingCurve.Type.OutQuart,
            on_finished=on_finished,
        )

    def collapse(
        self, extra_animations=None, duration=300, easing=None, on_finished=None
    ):
        """收起网格高度到 0

        Args:
            extra_animations: 与网格并行执行的附加动画，格式为
                [(widget, start_height, end_height), ...]
            duration: 动画时长（毫秒）
            easing: 缓动曲线，默认 OutQuart
            on_finished: 动画完成回调
        """
        current_height = self.height()

        animations = [(self, current_height, 0)]
        if extra_animations:
            animations.extend(extra_animations)

        self._animator.animate_heights(
            animations,
            duration=duration,
            easing=easing or QEasingCurve.Type.OutQuart,
            on_finished=on_finished,
        )

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
                        btn.setBgColor("accent")
                    else:
                        btn.setBgColor(self._idle_bg)
        callback(selected_text)
        self.item_selected.emit(selected_text)
