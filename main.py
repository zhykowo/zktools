import sys
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QGraphicsOpacityEffect

from utils.DragDropMixin import DragDropMixin
from utils.ClipboardMonitor import ClipboardMonitor

from widgets.CoreButton import CoreButton
from widgets.SvgButton import SvgButton

from core.page_controller import PageController, SwitchMode
from core.window_manager import WindowManager
from core.page_animation import PageAnimationManager
from core.hotkey_manager import HotkeyManager

from pages.base_page import BasePage

from scripts.switch_touchpad.main import run_switch_touchpad
# ==========================================
# 0. 路由行为状态与控制信号
# ==========================================

class OnDragEvent(QObject):
    on_drag_event = Signal(bool)

page_signals = PageController()
on_drag_bus = OnDragEvent()

# ==========================================
# 1. 独立的子页面类
# ==========================================

class HomePage(DragDropMixin, BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_drag_drop()

        self.target_size = (100, 50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 设置按钮 (齿轮)
        svg_settings = """
        <svg viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
        """

        setting_btn = SvgButton(size=30, icon_size=24, svg_data=svg_settings)
        setting_btn.clicked.connect(lambda: page_signals.immediate_switch("setting"))

        self.drop_hint_label = QLabel("Drag here", self)
        self.drop_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint_label.setStyleSheet("color: rgba(0, 0, 0, 0); font-size: 18px; border: 2px dashed grey; border-radius: 5px; ")

        self.drop_hint_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.drop_hint_label.setMaximumWidth(0) 

        layout.addWidget(setting_btn)
        layout.addWidget(self.drop_hint_label)

        self.drop_anim = QPropertyAnimation(self.drop_hint_label, b"maximumWidth")
        self.drop_anim.setDuration(800)
        self.drop_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

    def on_drag_enter(self):
        self.drop_hint_label.setStyleSheet("color: white; font-size: 18px; border: 2px dashed grey; border-radius: 5px; ")

        on_drag_bus.on_drag_event.emit(True)
        self.drop_anim.stop()
        self.drop_anim.setEndValue(0)
        self.drop_anim.start()

    def on_drag_leave(self):
        on_drag_bus.on_drag_event.emit(False)
        self.drop_anim.stop()
        self.drop_anim.setEndValue(0)
        self.drop_anim.start()
        
    # def on_files_dropped(self, file_paths: list[str]):
    #     pass


class SettingPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = QVBoxLayout(self)
        back_btn = CoreButton("⬅️ Back", self)
        back_btn.clicked.connect(lambda: page_signals.exit_self())

        title = QLabel("⚙️ 这是设置页面", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft) 
        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()
    


class ShortTextPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.start_thread()
        self.target_size = (200, 50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("", self)
        # label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.label)

    def start_thread(self):

        # 3. 创建线程和工作者
        self.thread = QThread()
        self.worker = ClipboardMonitor()

        # 4. 将工作者移动到新线程
        self.worker.moveToThread(self.thread)

        # 5. 连接信号与槽
        # 线程启动时，执行工作者的耗时方法
        self.thread.started.connect(self.worker.start)
        
        # 接收工作者的进度信号，更新 UI
        self.worker.cbChanged.connect(self.update_ui)
        
        # 清理线程
        # self.worker.finished.connect(self.thread.quit)
        # self.worker.finished.connect(self.worker.deleteLater)
        # self.thread.finished.connect(self.thread.deleteLater)

        # 6. 启动线程
        self.thread.start()
    
    def quit_msg(self):
        page_signals.exit_self()

    @Slot()
    def update_ui(self):
        page_signals.immediate_switch("short_text")
        self.label.setText("Copied!")
        QTimer.singleShot(1500, self.quit_msg)

class SwitchTouchpadPage(BasePage):
    # 1. 明确定义一个 Qt 信号，用于将子线程的触发通知安全送回主线程
    trigger_switch_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.hotkey_manager = None
        self.current_struct = "Disabled"
        
        # 2. 将此信号绑定到主线程安全的执行函数上
        self.trigger_switch_signal.connect(self.on_hotkey_triggered)
        
        self.start()
        
        self.target_size = (250, 50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

    def action_a(self):
        print("\n💥 触发了测试动作 (Ctrl + Alt + A)")

    def quit_msg(self):
        page_signals.exit_self()

    def update_text(self):
        if self.current_struct:
            self.label.setText(f"TouchPad {self.current_struct}")
            page_signals.immediate_switch("switch_touchpad")

    def switch_action(self):
        if self.current_struct == "Disabling" or self.current_struct == "Enabling":
            return

        # 发射信号，通知主线程
        self.trigger_switch_signal.emit()

        if self.current_struct == "Enabled":
            self.current_struct = "Disabling"
            run_switch_touchpad(enable=False)
            self.current_struct = "Disabled"

        elif self.current_struct == "Disabled":
            self.current_struct = "Enabling"
            run_switch_touchpad(enable=True)
            self.current_struct = "Enabled"

        self.quit_msg()
        self.trigger_switch_signal.emit()




    # 4. 这个槽函数由信号触发，会自动在【主线程】中执行
    @Slot()
    def on_hotkey_triggered(self):
        # 此时已经安全回到主线程，可以放心操作 UI 和 QTimer
        self.update_text()
        QTimer.singleShot(3000, self.quit_msg) 

    def start(self):
        self.manager = HotkeyManager()
        self.manager.register("ctrl+alt+a", self.action_a)
        self.manager.register("ctrl+shift+b", self.switch_action)
        self.manager.start()


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

        self.stacked_widget = QStackedWidget(self.main_container)

        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)

        self.register_page("home", HomePage())
        self.register_page("setting", SettingPage())
        self.register_page("short_text", ShortTextPage())
        self.register_page("switch_touchpad", SwitchTouchpadPage())

        self.current_page_name = "home"
        self.stacked_widget.setCurrentWidget(self.pages["home"])

        svg_close = """
        <svg viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
        """

        close_btn = SvgButton(size=30, icon_size=24, svg_data=svg_close)
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
            if self.current_page_name is None:
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
    # 4. 动画过渡实现（已组件化）
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