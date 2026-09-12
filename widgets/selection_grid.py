# selection_grid.py
"""可复用的按钮选择网格组件"""

from PySide6.QtCore import Property, QEasingCurve, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QWidget

from widgets.core_button import CoreButton
from widgets.widget_animator import WidgetAnimator


class SelectionGrid(QWidget):
    item_selected = Signal(str)

    def __init__(
        self,
        cols: int = 3,
        item_height: int = 36,
        spacing: int = 8,
        parent=None,
    ):
        super().__init__(parent)
        self._cols = cols
        self._item_height = item_height
        self._spacing = spacing

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(self._spacing)

        self.setMinimumHeight(0)
        self.setMaximumHeight(0)

        self._animator = WidgetAnimator(self)

        # 使用 QButtonGroup 管理网格内按钮的原生互斥单选
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(self._on_button_clicked)

        self._current_trigger = None
        self._on_select_callback = None

    # ==================== 可动画化的高度属性 ====================
    def _get_anim_height(self):
        return self.height()

    def _set_anim_height(self, h):
        self.setFixedHeight(h)

    anim_height = Property(int, _get_anim_height, _set_anim_height)

    @property
    def is_expanded(self) -> bool:
        return self._current_trigger is not None

    # ==================== 公共核心接口 ====================

    def toggle(self, trigger_btn, items: list[str], current_value: str, callback, extra_animations=None):
        """联动触发按钮，执行网格的展开、切换与收起

        外部只需将点击的按钮实例传入，该方法会依据按钮的 isChecked 状态自动处理展开与折叠。
        """
        # 1. 切换不同按钮时，将上一个触发按钮的状态置反
        if self._current_trigger and self._current_trigger != trigger_btn:
            if self._current_trigger.isCheckable():
                self._current_trigger.setChecked(False)

        # 2. 依据原生 checkable 状态决定展开还是收起
        # (若是原生 Checkable 按钮，点击时 Qt 已自动 toggle 其状态)
        if trigger_btn.isChecked() or not trigger_btn.isCheckable() and self._current_trigger != trigger_btn:
            self._current_trigger = trigger_btn
            if self._current_trigger.isCheckable():
                self._current_trigger.setChecked(True)

            self._on_select_callback = callback
            self._populate(items, current_value)
            self._expand_to(len(items), extra_animations)
        else:
            self.collapse(extra_animations)

    def collapse(self, extra_animations=None, duration=300, easing=None, on_finished=None):
        """收起网格，并重置触发按钮的选中状态"""
        if self._current_trigger:
            if self._current_trigger.isCheckable():
                self._current_trigger.setChecked(False)
            self._current_trigger = None

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

    # ==================== 内部方法 ====================

    def _populate(self, items: list[str], current_value: str):
        self._clear()
        for idx, text in enumerate(items):
            btn = CoreButton(text)
            btn.setCheckable(True)  # 开启原生选中属性
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            if text == current_value:
                btn.setChecked(True)

            self.button_group.addButton(btn, idx)
            row, col = divmod(idx, self._cols)
            self.grid_layout.addWidget(btn, row, col)

    def _on_button_clicked(self, btn):
        selected_text = btn.text()
        if self._on_select_callback:
            self._on_select_callback(selected_text)
        self.item_selected.emit(selected_text)

    def _expand_to(self, item_count: int, extra_animations=None, duration=300, easing=None, on_finished=None):
        cols = self._cols
        rows = (item_count + cols - 1) // cols
        target_height = rows * self._item_height + (rows - 1) * self._spacing
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

    def _clear(self):
        # 移除 QButtonGroup 中的关联
        for btn in self.button_group.buttons():
            self.button_group.removeButton(btn)

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
