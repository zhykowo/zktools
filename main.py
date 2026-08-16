import sys
from PySide6.QtCore import QEvent, QVariantAnimation, Qt
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStackedWidget, QGraphicsOpacityEffect
from PySide6.QtGui import QFont, QPalette

from core.page_router import page_router
from core.window_manager import WindowManager, drag_bus
from core.page_animation import PageAnimationManager

import utils.text_manager as text_manager
import utils.clipboard_monitor as clipboard_monitor
from utils.mouse_tracker import MouseHoverEventFilter

from widgets.main_container import MainContainerWidget

from resources.colors import WHITE

from pages.homepage import HomePage, on_drag_bus
from pages.setting_page import SettingPage
from pages.clipboard_ctl_page import ClipboardCtlPage
from pages.touchpad_ctl_page import TouchpadCtlPage
from pages.module_center_page import ModuleCenterPage
from pages.translator_page import TranslatorPage
from pages.note_page import NotePage



# 主窗口类
class MainShellWindow(QWidget):
    def __init__(self):
        super().__init__()

        # 页面状态与切换逻辑统一托管在 page_router 单例中（见 core/page_router.py），
        # 子模块可直接导入读取或发起切换，无需经由此窗口实例。

        # 绑定全新的中心调度器
        on_drag_bus.on_drag_event.connect(self.change_drag_state)

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.MAX_W, self.MAX_H = 450, 400
        self.resize(self.MAX_W, self.MAX_H)

        # self.init_island_movement()
        self.window_manager = WindowManager(self)
        drag_bus.register_drag_handle_requested.connect(
            self.window_manager.register_drag_handle
        ) # 监听全局拖拽注册请求
        
        self.init_ui()

    def register_page(self, name: str, widget: QWidget):
        """动态注册页面，方便未来无缝扩展更多页面"""
        page_router.pages[name] = widget
        page_router.pages[name].page_name = name
        self.stacked_widget.addWidget(widget)

    def change_drag_state(self, state):
        pass


    def init_ui(self):

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, WHITE)
        self.setPalette(palette)

        font = QFont()
        font.setPointSize(12)
        self.setFont(font)
        
        self.main_container = MainContainerWidget(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.installEventFilter(self)

        container_layout = QHBoxLayout(self.main_container)
        container_layout.setContentsMargins(10, 0, 10, 0)
        container_layout.setSpacing(5)

        self.stacked_widget = QStackedWidget(self.main_container)

        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)

        # 注册名统一取自各页面的 PAGE_NAME 类属性（页面三名称之一，见 pages/base_page.py）
        self.register_page(HomePage.PAGE_NAME, HomePage())
        self.register_page(SettingPage.PAGE_NAME, SettingPage())
        self.register_page(ClipboardCtlPage.PAGE_NAME, ClipboardCtlPage())
        self.register_page(TouchpadCtlPage.PAGE_NAME, TouchpadCtlPage())
        self.register_page(ModuleCenterPage.PAGE_NAME, ModuleCenterPage())
        self.register_page(TranslatorPage.PAGE_NAME, TranslatorPage())
        self.register_page(NotePage.PAGE_NAME, NotePage())

        page_router.page_queue = ["home"]   # 队首即当前页，初始为 home
        self.stacked_widget.setCurrentWidget(page_router.pages["home"])

        container_layout.addWidget(self.stacked_widget)
        
        start_w, start_h = page_router.pages["home"].target_size
        self.main_container.setGeometry(
            (self.MAX_W - start_w) // 2, 
            40, 
            start_w, 
            start_h
        )

        # 动画管理器设置
        self.animation_manager = PageAnimationManager(
            container_widget=self.main_container,
            stacked_widget=self.stacked_widget,
            opacity_effect=self.opacity_effect,
            max_width=self.MAX_W,
            max_height=self.MAX_H
        )

        # 设置圆角更新回调
        self.animation_manager.on_radius_update = self.update_container_radius
        self.update_container_radius(25)
        self.create_anim()

        # 将窗口/动画管理器注入路由单例，路由请求由 core.page_router 统一调度
        page_router.bind(
            window_manager=self.window_manager,
            animation_manager=self.animation_manager,
        )

    def update_container_radius(self, radius):
        """原生更新容器圆角"""
        self.main_container.set_radius(radius)

    def eventFilter(self, watched, event):
        """当鼠标进入灵动岛容器时触发闪烁"""
        if watched == self.main_container and event.type() == QEvent.Type.Enter:
            text_manager.get().get_selected_text()
            self.trigger_flash_effect()
        return super().eventFilter(watched, event)

    def create_anim(self):
        # 创建颜色渐变动画
        self._flash_anim = QVariantAnimation(self)
        self._flash_anim.setDuration(220)  # 闪烁持续时间 (毫秒)
        self._flash_anim.setStartValue(self.main_container.default_background_color.lighter(255))  # 闪烁高亮颜色
        self._flash_anim.setEndValue(self.main_container.default_background_color)    # 恢复基础背景色

        self._flash_anim.valueChanged.connect(self.main_container.set_background_color)

    def trigger_flash_effect(self):
        """灵动岛高亮脉冲闪烁动画"""
        if page_router.page_queue and page_router.page_queue[0] != 'home':
            return
        # 防止动画重复叠加
        if hasattr(self, "_flash_anim") and self._flash_anim.state() == QVariantAnimation.State.Running:
            return

        self._flash_anim.start()

    def changeEvent(self, event):
        # 当窗口的激活状态发生改变时触发
        if event.type() == QEvent.Type.ActivationChange:
            self.window_manager.handle_focus_change(self.isActiveWindow())


if __name__ == "__main__":

    app = QApplication(sys.argv)

    # 通过 QFont 修正字体渲染
    font = app.font()
    # PreferQuality：匹配字体时，选择最接近的标准点大小
    # PreferAntialias：渲染时，尽可能开启抗锯齿
    font.setStyleStrategy(QFont.StyleStrategy.PreferQuality | QFont.StyleStrategy.PreferAntialias)  # 开启高质量抗锯齿
    font.setHintingPreference(
        QFont.HintingPreference.PreferNoHinting
    )  # 禁用硬网格对齐，消除发锯齿/粗细不均

    app.setFont(font)

    clipboard_monitor.init()
    text_manager.init()
    
    # 安装全局鼠标追踪事件过滤器 
    # 创建过滤器实例，debug_enabled=True 表示启用调试输出
    mouse_tracker = MouseHoverEventFilter(debug_enabled=False)
    app.installEventFilter(mouse_tracker)
    
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())