import sys
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QParallelAnimationGroup, QSequentialAnimationGroup, Property
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QGraphicsOpacityEffect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

# 如果你本地没有 utils.DragDropMixin，测试时可以先用下面这行 Mock
# class DragDropMixin: def init_drag_drop(self): pass
from utils.DragDropMixin import DragDropMixin

class CoreButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

    def paintEvent(self, event):
        # 抛弃默认绘制，自己用 QPainter 描绘一切
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿

        # 1. 根据状态决定颜色
        if not self.isEnabled():
            bg_color = QColor("#2c3e50")
        elif self.underMouse():  # Hover 状态
            bg_color = QColor("#415b76")
        else:                   # 正常状态
            bg_color = QColor("#34495e")

        # 特殊处理退出按钮颜色
        if self.objectName() == "CloseBtn":
            bg_color = QColor("#c0392b") if self.underMouse() else QColor("#e74c3c")

        # 2. 核心：动态计算当前按钮高度允许的最大圆角 (绝对不坍塌)
        radius = self.height() // 2 - 1

        # 3. 绘制背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(self.rect(), radius, radius)

        # 4. 绘制文字
        painter.setPen(QPen(QColor("white")))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())



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
        self.setting_btn = CoreButton("Setting", self)
        self.title = QLabel("拖放到此处", self)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: white; font-size: 18px; border: 2px dashed grey; border-radius: 5px; ")

        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.title.setMaximumWidth(0) 

        layout.addWidget(self.setting_btn)
        layout.addWidget(self.title)

        self.title_anim = QPropertyAnimation(self.title, b"maximumWidth")
        self.title_anim.setDuration(800)
        self.title_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

    def on_drag_enter(self):
        self.title_anim.stop()
        self.title_anim.setEndValue(200)
        self.title_anim.start()

    def on_drag_leave(self):
        self.title_anim.stop()
        self.title_anim.setEndValue(0)
        self.title_anim.start()
        
    # def on_files_dropped(self, file_paths: list[str]):
    #     self.title_anim.stop()
    #     self.title_anim.setEndValue(0)
    #     self.title_anim.start()


class SettingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 300)

        layout = QVBoxLayout(self)
        self.back_btn = CoreButton("⬅️ Back", self)
        title = QLabel("⚙️ 这是设置页面", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 18px;")
        layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft) 
        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()


# ==========================================
# 2. 主窗口类
# ==========================================
class MainShellWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.MAX_W, self.MAX_H = 450, 350
        self.resize(self.MAX_W, self.MAX_H) 

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

    def init_ui(self):
        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
        container_layout = QHBoxLayout(self.main_container)
        
        self.stacked_widget = QStackedWidget(self.main_container)
        self.home_page = HomePage()
        self.setting_page = SettingPage()
        self.stacked_widget.addWidget(self.home_page)     
        self.stacked_widget.addWidget(self.setting_page)  
        
        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)
        
        self.home_page.setting_btn.clicked.connect(lambda: self.switch_page_to(self.setting_page))
        self.setting_page.back_btn.clicked.connect(lambda: self.switch_page_to(self.home_page))

        close_btn = CoreButton("Exit", self.main_container)
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(QApplication.instance().quit)
        
        container_layout.addWidget(self.stacked_widget)
        container_layout.addWidget(close_btn)
        
        start_w, start_h = self.home_page.target_size
        self.main_container.setGeometry(
            (self.MAX_W - start_w) // 2, 
            (self.MAX_H - start_h) // 2, 
            start_w, 
            start_h
        )

        self.setStyleSheet("""
            QPushButton { padding: 8px; }
            QPushButton#CloseBtn { width: 50px; }
        """)
        
        self.container_radius = 25

    def switch_page_to(self, target_page_widget):
        index = self.stacked_widget.indexOf(target_page_widget)
        
        target_w, target_h = target_page_widget.target_size

        end_x = (self.MAX_W - target_w) // 2
        end_y = (self.MAX_H - target_h) // 2
        
        # --- 轨道 A：尺寸动画 ---
        size_anim = QPropertyAnimation(self.main_container, b"geometry")
        size_anim.setDuration(500)
        size_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        size_anim.setEndValue(QRect(end_x, end_y, target_w, target_h))
        size_anim.valueChanged.connect(self.on_frame_changed)
        
        # --- 轨道 C：透明度串行组合 ---
        fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out_anim.setDuration(400)
        fade_out_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out_anim.setEndValue(0.0)
        
        fade_out_anim.finished.connect(lambda: self.stacked_widget.setCurrentIndex(index))
        
        fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in_anim.setDuration(200)
        fade_in_anim.setEndValue(1.0)
        
        opacity_timeline = QSequentialAnimationGroup()
        opacity_timeline.addAnimation(fade_out_anim)
        opacity_timeline.addAnimation(fade_in_anim)
        
        # --- 总控并行组 ---
        self.master_timeline = QParallelAnimationGroup(self)
        self.master_timeline.addAnimation(size_anim)
        self.master_timeline.addAnimation(opacity_timeline) 
        
        self.master_timeline.start()

    def on_frame_changed(self, current_rect):
        # print(f"当前动画实时高度: {current_rect.height()}")
        self.container_radius = min(25, current_rect.height() // 2 - 1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())