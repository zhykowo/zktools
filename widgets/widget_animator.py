"""通用控件动画工具

使用自定义 ``anim_height`` 属性动画（类似 test.py 的方式）驱动控件高度变化，
动画过程中通过 ``setFixedHeight`` 改变控件高度，不再同时修改
MinimumHeight / MaximumHeight。

用法::

    animator = WidgetAnimator(self)
    animator.animate_heights(
        [(widget_a, 0, 120), (widget_b, 100, 0)],
        duration=300,
        on_finished=some_callback,
    )
"""

from collections.abc import Sequence

from PySide6.QtCore import QEasingCurve, QObject, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import QWidget


class WidgetAnimator(QObject):
    """控件动画管理器

    支持并行动画多个控件的高度，每个控件必须暴露 ``anim_height`` 属性
    （通过 ``setFixedHeight`` 实现）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_group = None

    def animate_heights(
        self,
        animations_data: Sequence[tuple[QWidget, int, int]],
        duration=300,
        easing=QEasingCurve.Type.OutQuart,
        on_finished=None,
    ):
        """并行动画多个控件的高度

        Args:
            animations_data: [(widget, start_height, end_height), ...]
                每个 widget 必须暴露 ``anim_height`` 属性。
            duration: 动画时长（毫秒）。
            easing: 缓动曲线。
            on_finished: 全部动画完成后的回调（仅执行一次）。
        """
        # 替换旧动画组，防止因 parent 指向常驻页面而泄漏
        if self._active_group is not None:
            self._active_group.stop()
            self._active_group.deleteLater()

        self._active_group = QParallelAnimationGroup(self)

        for widget, start_h, end_h in animations_data:
            # 固定起始高度，为动画做准备
            widget.setFixedHeight(start_h)

            anim = QPropertyAnimation(widget, b"anim_height", self._active_group)
            anim.setDuration(duration)
            anim.setStartValue(start_h)
            anim.setEndValue(end_h)
            anim.setEasingCurve(easing)

            self._active_group.addAnimation(anim)

        if on_finished:
            self._active_group.finished.connect(on_finished)

        self._active_group.start()

    def stop(self):
        """停止当前动画"""
        if self._active_group is not None:
            self._active_group.stop()