import sys
from PySide6.QtCore import QEvent, QVariantAnimation, Qt
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStackedWidget, QGraphicsOpacityEffect
from PySide6.QtGui import QFont, QPalette

from core.page_controller import SwitchMode, page_signals
from core.window_manager import WindowManager, drag_bus
from core.page_animation import PageAnimationManager

from resources.svgs import close_icon

import utils.text_manager as text_manager
import utils.clipboard_monitor as clipboard_monitor
from utils.mouse_tracker import MouseHoverEventFilter

from widgets.svg_button import SvgButton
from widgets.main_container import MainContainerWidget

from pages.homepage import HomePage, on_drag_bus
from pages.setting_page import SettingPage
from pages.clipboard_ctl_page import ClipboardCtlPage
from pages.touchpad_ctl_page import TouchpadCtlPage
from pages.module_center_page import ModuleCenterPage
from pages.translator_page import TranslatorPage



# 主窗口类
class MainShellWindow(QWidget):
    def __init__(self):
        super().__init__()

        # 核心数据结构维护
        self.pages = {}              # 页面注册池 { "page_name": widget_instance }
        self.page_queue = []         # 页面切换等待队列 [page_name, ...]
        self.current_page_name = None # 当前正在显示的页面

        # 绑定全新的中心调度器
        page_signals.page_action.connect(self.handle_page_action)
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
        self.pages[name] = widget
        self.stacked_widget.addWidget(widget)

    def change_drag_state(self, state):
        pass


    def init_ui(self):

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
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

        self.register_page("home", HomePage())
        self.register_page("setting", SettingPage())
        self.register_page("short_text", ClipboardCtlPage())
        self.register_page("switch_touchpad", TouchpadCtlPage())
        self.register_page("module_center", ModuleCenterPage())
        self.register_page("translator", TranslatorPage())

        self.current_page_name = "home"
        self.stacked_widget.setCurrentWidget(self.pages["home"])

        close_btn = SvgButton(size=36, icon_size=24, svg_data=close_icon, hover_color="#E81123", enable_rotation=True)
        close_btn.clicked.connect(QApplication.instance().quit)
        
        container_layout.addWidget(self.stacked_widget)
        container_layout.addWidget(close_btn)
        
        start_w, start_h = self.pages["home"].target_size
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
        if not self.current_page_name == 'home':
            return
        # 防止动画重复叠加
        if hasattr(self, "_flash_anim") and self._flash_anim.state() == QVariantAnimation.State.Running:
            return

        self._flash_anim.start()

    # 核心队列与路由调度逻辑
    def handle_page_action(self, mode: SwitchMode, page_name: str):
        """核心路由控制阀"""

        self.window_manager.queue_state = True
        self.window_manager.animate(True)

        if mode == SwitchMode.GENTLE:
            # 1. 温和切换：仅塞入队列
            self.page_queue.append(page_name)
            # 如果当前没有任何页面在渲染（处于空闲），则直接触发下一页
            if self.current_page_name is None or self.current_page_name == "home":
                self.next_page()

        elif mode == SwitchMode.IMMEDIATE:
            # 2. 立即切换：插队逻辑
            if page_name not in self.pages: return
            
            if self.current_page_name is not None:
                # 把当前未"退出自己"的页面重新塞回队列的最前端，等新页面退出后能无缝恢复
                self.page_queue.insert(0, self.current_page_name)
                
            self.current_page_name = page_name

            self.pages[page_name].on_show()
            self.animation_manager.switch_to(self.pages[page_name])
            
        elif mode == SwitchMode.EXIT_SELF:
            if self.current_page_name:
                current_page = self.pages.get(self.current_page_name)
                if current_page and hasattr(current_page, 'clear_data'):
                    current_page.clear_data()
            self.next_page()
            
    def next_page(self):
        """从队列中提取并渲染下一个页面"""
        if self.page_queue:
            next_name = self.page_queue.pop(0)
            self.current_page_name = next_name
            self.pages[next_name].on_show()
            self.animation_manager.switch_to(self.pages[next_name])
            if next_name == "home":
                self.window_manager.queue_state = False
                # 归位居中显示
                self.window_manager.animate(show=self.window_manager.on_focus, recenter=True)
        else:
            # 队列完全清空
            self.current_page_name = "home"
            self.window_manager.queue_state = False
            # 归位居中显示
            self.window_manager.animate(show=self.window_manager.on_focus, recenter=True)

    def changeEvent(self, event):
        # 当窗口的激活状态发生改变时触发
        if event.type() == QEvent.Type.ActivationChange:
            self.window_manager.handle_focus_change(self.isActiveWindow())


if __name__ == "__main__":

    app = QApplication(sys.argv)

    clipboard_monitor.init()
    text_manager.init()
    
    # 安装全局鼠标追踪事件过滤器 
    # 创建过滤器实例，debug_enabled=True 表示启用调试输出
    mouse_tracker = MouseHoverEventFilter(debug_enabled=False)
    app.installEventFilter(mouse_tracker)
    
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())