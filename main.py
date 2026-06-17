from enum import Enum, auto
import sys
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QThread, QTimer, Qt, QParallelAnimationGroup, QSequentialAnimationGroup, Property, Signal, Slot
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QGraphicsOpacityEffect

from utils.DragDropMixin import DragDropMixin
from widgets.CoreButton import CoreButton
from utils.ClipboardMonitor import ClipboardMonitor

# ==========================================
# 0. 路由行为状态与控制信号
# ==========================================
class SwitchMode(Enum):
    GENTLE = auto()    # 温和切换：加入队列排队
    IMMEDIATE = auto() # 立即切换：插队并强制中断当前页面
    EXIT_SELF = auto() # 退出自己：当前页面结束，释放并展示队列下一页

class PageController(QObject):
    # 统一信号：传递 切换模式 和 目标页面标识
    page_action = Signal(object, str) 

    def gentle_switch(self, page_name: str):
        """温和切换：仅加入队列"""
        self.page_action.emit(SwitchMode.GENTLE, page_name)

    def immediate_switch(self, page_name: str):
        """立即切换：立刻中断并显示目标页"""
        self.page_action.emit(SwitchMode.IMMEDIATE, page_name)

    def exit_self(self):
        """退出自己：通知调度器调度下一页"""
        self.page_action.emit(SwitchMode.EXIT_SELF, "")

class OnDragEvent(QObject):
    on_drag_event = Signal(bool)

page_signals = PageController()
on_drag_bus = OnDragEvent()

# ==========================================
# 1. 独立的子页面类
# ==========================================

class HomePage(DragDropMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_drag_drop()

        self.target_size = (400, 50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        setting_btn = CoreButton("Setting", self)
        setting_btn.clicked.connect(lambda: page_signals.immediate_switch("setting"))

        self.drop_hint_label = QLabel("拖放到此处", self)
        self.drop_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint_label.setStyleSheet("color: white; font-size: 18px; border: 2px dashed grey; border-radius: 5px; ")

        self.drop_hint_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.drop_hint_label.setMaximumWidth(200) 

        layout.addWidget(setting_btn)
        layout.addWidget(self.drop_hint_label)

        self.drop_anim = QPropertyAnimation(self.drop_hint_label, b"maximumWidth")
        self.drop_anim.setDuration(800)
        self.drop_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

    def on_drag_enter(self):
        on_drag_bus.on_drag_event.emit(True)
        self.drop_anim.stop()
        self.drop_anim.setEndValue(200)
        self.drop_anim.start()

    def on_drag_leave(self):
        on_drag_bus.on_drag_event.emit(False)
        self.drop_anim.stop()
        self.drop_anim.setEndValue(200)
        self.drop_anim.start()
        
    # def on_files_dropped(self, file_paths: list[str]):
    #     pass

    def on_show(self):
        pass

class SettingPage(QWidget):
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
    
    def on_show(self):
        pass

class ShortTextPage(QWidget):
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

    def on_show(self):
        # self.label.setText("这是文字")
        pass


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
        
        self.MAX_W, self.MAX_H = 450, 350
        self.resize(self.MAX_W, self.MAX_H)


        self.init_island_movement()
        self.init_ui()

    # 定义响应 Qt 动画系统的 Property
    @Property(int)
    def container_radius(self):
        return self._container_radius

    @container_radius.setter
    def container_radius(self, value):
        self._container_radius = value
        # 刷新 MainContainer 的 QSS 规则
        if hasattr(self, 'main_container'):
            self.main_container.setStyleSheet(f"""
                QWidget#MainContainer {{ 
                    background-color: black; 
                    border-radius: {value}px; 
                }}
            """)

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

        self.current_page_name = "home"
        self.stacked_widget.setCurrentWidget(self.pages["home"])

        close_btn = CoreButton("Exit", self.main_container)
        close_btn.setObjectName("CloseBtn")
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

        self.container_radius = 25

    # ==========================================
    # 3. 核心队列与路由调度逻辑
    # ==========================================
    def handle_page_action(self, mode: SwitchMode, page_name: str):
        """核心路由控制阀"""

        self.queue_state = True
        self.animate_island(True)

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
            self.switch_page_to(self.pages[page_name])
            
        elif mode == SwitchMode.EXIT_SELF:
            # 3. 退出自己：交出控制权，加载队列中的下一个页面
            self.next_page()

    def next_page(self):
        """从队列中提取并渲染下一个页面"""
        if self.page_queue:
            next_name = self.page_queue.pop(0)
            self.current_page_name = next_name
            self.switch_page_to(self.pages[next_name])
            if next_name == "home":
                self.queue_state = False
                self.animate_island(False)
        else:
            # 队列完全清空
            self.current_page_name = "home"
            self.queue_state = False
            self.animate_island(False)

    # ==========================================
    # 4. 动画过渡实现
    # ==========================================
    def switch_page_to(self, target_page_widget):
        # 1. 检查并打断正在运行的旧动画
        if hasattr(self, 'master_timeline') and self.master_timeline is not None:
            # 停止总控制组，它会自动停止内部包含的所有子动画
            self.master_timeline.stop()
            # 显式解除之前的连接，防止打断时触发旧的 finished 槽函数
            # （虽然 stop() 不会触发 finished，但解绑是个更安全的防御性习惯）
            try:
                self.master_timeline.disconnect()
            except TypeError:
                pass

        index = self.stacked_widget.indexOf(target_page_widget)
        target_w, target_h = target_page_widget.target_size

        end_x = (self.MAX_W - target_w) // 2
        end_y = 40
        
        # 2. 动态捕获当前状态作为起始值（实现平滑过渡的关键）
        current_geometry = self.main_container.geometry()
        current_opacity = self.opacity_effect.opacity()

        # --- 轨道 A：尺寸动画 ---
        size_anim = QPropertyAnimation(self.main_container, b"geometry")
        size_anim.setDuration(500)
        size_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        size_anim.setStartValue(current_geometry) # 设置当前位置为起点
        size_anim.setEndValue(QRect(end_x, end_y, target_w, target_h))
        size_anim.valueChanged.connect(self.on_frame_changed)
        
        # --- 轨道 C：透明度串行组合 ---
        # 优化：计算淡出阶段剩余的时间（能让高频连点时动画更自然）
        fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out_anim.setDuration(int(400 * current_opacity)) # 根据当前透明度缩短淡出时间
        fade_out_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out_anim.setStartValue(current_opacity) # 设置当前透明度为起点
        fade_out_anim.setEndValue(0.0)
        
        # 使用 lambda 传递当前 index，确保即使 index 变了也能切到正确的页面
        fade_out_anim.finished.connect(lambda i=index: self.stacked_widget.setCurrentIndex(i))
        target_page_widget.on_show()
        
        fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in_anim.setDuration(200)
        fade_in_anim.setStartValue(0.0)
        fade_in_anim.setEndValue(1.0)
        
        # 为了防止内存泄漏，将动画组的父级设为 self
        opacity_timeline = QSequentialAnimationGroup(self)
        opacity_timeline.addAnimation(fade_out_anim)
        opacity_timeline.addAnimation(fade_in_anim)
        
        # --- 总控并行组 ---
        self.master_timeline = QParallelAnimationGroup(self)
        self.master_timeline.addAnimation(size_anim)
        self.master_timeline.addAnimation(opacity_timeline) 
        
        # 3. 动画完成后自动清理，释放内存
        self.master_timeline.finished.connect(self._clear_animation)
        
        self.master_timeline.start()

    def _clear_animation(self):
        """动画正常结束后的清理函数"""
        if hasattr(self, 'master_timeline') and self.master_timeline is not None:
            self.master_timeline.deleteLater()
            self.master_timeline = None

    def on_frame_changed(self, current_rect):
        # print(f"当前动画实时高度: {current_rect.height()}")
        self.container_radius = min(25, current_rect.height() // 2 - 1)
    
    def init_island_movement(self):

        self.on_focus = False
        self.queue_state = False

        self.visible_height = 280
        self.screen_geometry = QApplication.primaryScreen().geometry()
        self.island_width = self.width()
        self.island_height = self.height()

        self.y_hidden = -self.island_height + self.visible_height
        self.y_shown = -30  # 贴着屏幕顶端完全显示

        self.x_center = (self.screen_geometry.width() - self.island_width) // 2

        # 4. 初始化窗口位置（默认隐藏，只留个底边）
        self.move(self.x_center, self.y_hidden)
        self.is_expanded = False
        
        # 5. 设置平滑动画
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(800)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def animate_island(self, show: bool):
        """执行上滑/下滑动画"""
        if self.is_expanded == show:
            return # 状态未改变，不重复触发动画
        elif self.is_expanded == True and show == False:
            if self.queue_state == True or self.on_focus == True:
                return

        self.is_expanded = show
        target_y = self.y_shown if show else self.y_hidden
        
        # 停止当前正在进行的动画，防止抽搐
        self.anim.stop()
        self.anim.setEndValue(QPoint(self.x_center, target_y))
        self.anim.start()

    def changeEvent(self, event):
        # 当窗口的激活状态发生改变时触发
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                print("窗口获得了焦点！")
                self.on_focus = True
                self.animate_island(True)
            else:
                print("窗口失去了焦点！")
                self.on_focus = False
                self.animate_island(False)

        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())