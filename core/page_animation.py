from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QSequentialAnimationGroup,
    QRect,
    Signal,
)
from PySide6.QtWidgets import QWidget
from typing import Callable, Optional, cast

from pages.base_page import BasePage


class PageAnimationManager(QObject):
    """页面切换动画管理器（QObject 以支持信号：页面暗下瞬间通知路由层执行 on_show）"""

    page_switched = Signal(str)  # 透明度完全暗下、已切到目标页索引时发出，携带页面名

    def __init__(
        self,
        container_widget,
        stacked_widget,
        opacity_effect,
        max_width=450,
        max_height=400,
    ):
        super().__init__()
        self.container = container_widget
        self.stacked_widget = stacked_widget
        self.opacity_effect = opacity_effect
        self.max_width = max_width
        self.max_height = max_height
        self.master_timeline = None
        self.on_radius_update: Optional[Callable[[int], None]] = None  # 圆角更新回调

    # ---------- 基础动画创建 ----------
    def _create_size_animation(self, start_geom, end_geom):
        """返回一个几何动画对象（未启动）"""
        anim = QPropertyAnimation(self.container, b"geometry")
        anim.setDuration(500)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.setStartValue(start_geom)
        anim.setEndValue(end_geom)
        return anim

    def _create_opacity_switch_animation(self, target_index, page_name):
        """返回透明度切换串行动画组（淡出→切换索引→淡入）"""
        current_opacity = self.opacity_effect.opacity()
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out.setDuration(int(400 * current_opacity))
        fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out.setStartValue(current_opacity)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(
            lambda: self._apply_page_switch(target_index, page_name)
        )

        fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        seq = QSequentialAnimationGroup(self.container)
        seq.addAnimation(fade_out)
        seq.addAnimation(fade_in)
        return seq

    # ---------- 公共接口 ----------
    def animate_size_to(self, target_w, target_h):
        """仅改变容器尺寸到指定宽高（不切换页面，不影响透明度）"""
        self._clear_animation()
        current_geom = self.container.geometry()
        end_x = (self.max_width - target_w) // 2
        end_y = 40
        end_geom = QRect(end_x, end_y, target_w, target_h)
        if current_geom == end_geom:
            return

        size_anim = self._create_size_animation(current_geom, end_geom)
        # 尺寸变化时更新圆角
        if self.on_radius_update:
            size_anim.valueChanged.connect(self._on_size_changed)

        self.master_timeline = size_anim
        self.master_timeline.finished.connect(self._clear_animation)
        self.master_timeline.start()

    def switch_to(self, target_page: QWidget, page_name: str):
        """组合动画：尺寸变化 + 透明度切换（透明度暗下瞬间发 page_switched 信号）"""
        self._clear_animation()
        index = self.stacked_widget.indexOf(target_page)
        target_w, target_h = cast(BasePage, target_page).target_size
        end_x = (self.max_width - target_w) // 2
        end_y = 40
        end_geom = QRect(end_x, end_y, target_w, target_h)
        current_geom = self.container.geometry()

        size_anim = self._create_size_animation(current_geom, end_geom)
        if self.on_radius_update:
            size_anim.valueChanged.connect(self._on_size_changed)

        opacity_switch = self._create_opacity_switch_animation(index, page_name)

        # 并行执行尺寸动画和透明度切换
        parallel = QParallelAnimationGroup(self.container)
        parallel.addAnimation(size_anim)
        parallel.addAnimation(opacity_switch)

        self.master_timeline = parallel
        self.master_timeline.finished.connect(self._clear_animation)
        self.master_timeline.start()

    # ---------- 内部辅助 ----------
    def _apply_page_switch(self, target_index, page_name):
        """透明度完全暗下的瞬间：切换堆叠索引，并通知路由层执行目标页 on_show"""
        self.stacked_widget.setCurrentIndex(target_index)
        self.page_switched.emit(page_name)

    def _on_size_changed(self, current_rect):
        if self.on_radius_update:
            radius = min(25, current_rect.height() // 2 - 1)
            self.on_radius_update(radius)

    def _clear_animation(self):
        if self.master_timeline is not None:
            self.master_timeline.stop()
            self.master_timeline.deleteLater()
            self.master_timeline = None
