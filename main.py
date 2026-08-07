import sys
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStackedWidget, QGraphicsOpacityEffect

from widgets.SvgButton import SvgButton

from core.page_controller import SwitchMode, page_signals
from core.window_manager import WindowManager
from core.page_animation import PageAnimationManager

from pages.homepage import HomePage, on_drag_bus
from pages.setting_page import SettingPage
from pages.clipboard_ctl_page import ClipboardCtlPage
from pages.touchpad_ctl_page import TouchpadCtlPage
from pages.app_center_page import AppCenterPage
from pages.tanslator_page import TranslatorPage

from resources.svgs import close_icon

# ==========================================
# 0. 路由行为状态与控制信号(已模块化)
# ==========================================

# ==========================================
# 1. 独立的子页面类(已模块化)
# ==========================================

# ==========================================
# 2. 主窗口类
# ==========================================
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

        self.init_ui()

    def register_page(self, name: str, widget: QWidget):
        """动态注册页面，方便未来无缝扩展更多页面"""
        self.pages[name] = widget
        self.stacked_widget.addWidget(widget)

    def change_drag_state(self, state):
        if state:
            window.activateWindow()


    def init_ui(self):
        
        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
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
        self.register_page("app_center", TranslatorPage())

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

        self.setStyleSheet("""
            QPushButton { padding: 8px; }
            QPushButton#CloseBtn { width: 50px; }
            QLabel { color: white; font-size: 16px; }
        """)

        # 在 init_ui() 之后
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

    def update_container_radius(self, radius):
        """更新容器圆角"""
        self.main_container.setStyleSheet(f"""
            QWidget#MainContainer {{ 
                background-color: #1d1d1f; 
                border-radius: {radius}px; 
            }}
        """)

    # ==========================================
    # 3. 核心队列与路由调度逻辑
    # ==========================================
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
                # 把当前未“退出自己”的页面重新塞回队列的最前端，等新页面退出后能无缝恢复
                self.page_queue.insert(0, self.current_page_name)
                
            self.current_page_name = page_name

            self.pages[page_name].on_show()
            self.animation_manager.switch_to(self.pages[page_name])
            
        elif mode == SwitchMode.EXIT_SELF:
            # 3. 退出自己：交出控制权，加载队列中的下一个页面
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
                self.window_manager.animate(False)
        else:
            # 队列完全清空
            self.current_page_name = "home"
            self.window_manager.queue_state = False
            self.window_manager.animate(False)

    # ==========================================
    # 4. 动画过渡实现（已模块化）
    # # ==========================================

    def changeEvent(self, event):
        # 当窗口的激活状态发生改变时触发
        if event.type() == QEvent.Type.ActivationChange:
            self.window_manager.handle_focus_change(self.isActiveWindow())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())