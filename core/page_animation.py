from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup, QRect
from PySide6.QtWidgets import QWidget

class PageAnimationManager:
    """页面切换动画管理器"""
    
    def __init__(self, container_widget, stacked_widget, opacity_effect, max_width=450, max_height=350):
        """
        Args:
            container_widget: 主容器（需要移动和缩放的widget）
            stacked_widget: 堆叠窗口（需要切换索引）
            opacity_effect: 透明度效果对象
            max_width: 窗口最大宽度
            max_height: 窗口最大高度
        """
        self.container = container_widget
        self.stacked_widget = stacked_widget
        self.opacity_effect = opacity_effect
        self.max_width = max_width
        self.max_height = max_height
        
        # 动画组引用
        self.master_timeline = None
        
        # 回调函数（用于解耦）
        self.on_radius_update = None  # 用于更新圆角
    
    def switch_to(self, target_page: QWidget):
        """
        执行页面切换动画
        
        Args:
            target_page: 目标页面widget
        """
        # 1. 停止并清理旧动画
        self._clear_animation()
        
        # 2. 准备动画参数
        index = self.stacked_widget.indexOf(target_page)
        target_w, target_h = target_page.target_size
        
        end_x = (self.max_width - target_w) // 2
        end_y = 40
        
        current_geometry = self.container.geometry()
        current_opacity = self.opacity_effect.opacity()
        
        # 3. 创建各个动画
        # 尺寸动画
        size_anim = self._create_size_animation(current_geometry, end_x, end_y, target_w, target_h)
        
        # 透明度动画（串行）
        opacity_timeline = self._create_opacity_animation(current_opacity, index)
        
        # 4. 组合并启动
        self.master_timeline = QParallelAnimationGroup(self.container)
        self.master_timeline.addAnimation(size_anim)
        self.master_timeline.addAnimation(opacity_timeline)
        
        # 连接清理信号
        self.master_timeline.finished.connect(self._clear_animation)
        
        # 如果设置了圆角更新回调，连接信号
        if self.on_radius_update:
            size_anim.valueChanged.connect(self._on_size_changed)
        
        self.master_timeline.start()
    
    def _create_size_animation(self, start_geometry, end_x, end_y, target_w, target_h):
        """创建尺寸变化动画"""
        anim = QPropertyAnimation(self.container, b"geometry")
        anim.setDuration(500)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.setStartValue(start_geometry)
        anim.setEndValue(QRect(end_x, end_y, target_w, target_h))
        return anim
    
    def _create_opacity_animation(self, current_opacity, target_index):
        """创建透明度动画（淡出+淡入）"""
        # 淡出
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out.setDuration(int(400 * current_opacity))
        fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out.setStartValue(current_opacity)
        fade_out.setEndValue(0.0)
        
        # 在淡出完成后切换页面
        fade_out.finished.connect(lambda: self.stacked_widget.setCurrentIndex(target_index))
        
        # 淡入
        fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        
        # 串行组合
        timeline = QSequentialAnimationGroup(self.container)
        timeline.addAnimation(fade_out)
        timeline.addAnimation(fade_in)
        return timeline
    
    def _on_size_changed(self, current_rect):
        """尺寸变化时的回调（更新圆角）"""
        if self.on_radius_update:
            radius = min(25, current_rect.height() // 2 - 1)
            self.on_radius_update(radius)
    
    def _clear_animation(self):
        """清理动画资源"""
        if self.master_timeline is not None:
            self.master_timeline.stop()
            self.master_timeline.deleteLater()
            self.master_timeline = None