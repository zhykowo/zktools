import sys
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QParallelAnimationGroup, QSequentialAnimationGroup
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QStackedWidget, QGraphicsOpacityEffect

# ==========================================
# 1. 独立的子页面类（保持不变）
# ==========================================
class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (300, 200)
        
        layout = QVBoxLayout(self)
        title = QLabel("🏠 这是主页面 (来自独立类)", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 18px;")
        self.next_btn = QPushButton("前往设置页面", self)
        layout.addWidget(title)
        layout.addWidget(self.next_btn)

class SettingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (450, 350)

        layout = QVBoxLayout(self)
        self.back_btn = QPushButton("⬅️ 返回主页", self)
        self.back_btn.setStyleSheet("QPushButton { max-width: 100px; font-size: 12px; }") 
        title = QLabel("⚙️ 这是设置页面 (来自独立类)", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 18px;")
        layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft) 
        layout.addStretch() 
        layout.addWidget(title)
        layout.addStretch() 


# ==========================================
# 2. 主窗口类（双通道时间轴版）
# ==========================================
class MainShellWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.MAX_W, self.MAX_H = 450, 350
        self.resize(self.MAX_W, self.MAX_H) 

        self.init_ui()

    def init_ui(self):
        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(self.main_container)
        
        self.stacked_widget = QStackedWidget(self.main_container)
        self.home_page = HomePage()
        self.setting_page = SettingPage()
        self.stacked_widget.addWidget(self.home_page)     
        self.stacked_widget.addWidget(self.setting_page)  
        
        # 【核心改动 1】：为堆栈窗口添加“透明度特效”组件，用来控制内容的明暗变幻
        self.opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.opacity_effect)
        
        self.home_page.next_btn.clicked.connect(lambda: self.switch_page_to(self.setting_page))
        self.setting_page.back_btn.clicked.connect(lambda: self.switch_page_to(self.home_page))

        close_btn = QPushButton("完全退出", self.main_container)
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(self.close)
        
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
            QWidget#MainContainer { background-color: black; border-radius: 15px; }
            QPushButton { background-color: #34495e; color: white; border-radius: 15px; padding: 8px; }
            QPushButton:hover { background-color: #415b76; }
            QPushButton#CloseBtn { background-color: #e74c3c; }
            QPushButton#CloseBtn:hover { background-color: #c0392b; }
        """)

    def switch_page_to(self, target_page_widget):
        """核心重构：动态读取子页面的 target_size 属性"""
        
        # 1. 动态获取目标页面在 QStackedWidget 中的索引
        index = self.stacked_widget.indexOf(target_page_widget)
        
        # 2. 【威力所在】：直接从子页面对象里读取它自己定义的尺寸！
        target_w, target_h = target_page_widget.target_size

        # 计算居中坐标
        end_x = (self.MAX_W - target_w) // 2
        end_y = (self.MAX_H - target_h) // 2
        
        # --- 轨道 A：尺寸动画 ---
        size_anim = QPropertyAnimation(self.main_container, b"geometry")
        size_anim.setDuration(500)
        size_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        size_anim.setStartValue(self.main_container.geometry())
        size_anim.setEndValue(QRect(end_x, end_y, target_w, target_h))
        
        # --- 轨道 B：透明度串行组合 ---
        fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out_anim.setDuration(400)
        fade_out_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out_anim.setStartValue(1.0)
        fade_out_anim.setEndValue(0.0)
        
        # 400ms 变暗结束，偷偷切页
        fade_out_anim.finished.connect(lambda: self.stacked_widget.setCurrentIndex(index))
        
        fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in_anim.setDuration(200)
        fade_in_anim.setStartValue(0.0)
        fade_in_anim.setEndValue(1.0)
        
        opacity_timeline = QSequentialAnimationGroup()
        opacity_timeline.addAnimation(fade_out_anim)
        opacity_timeline.addAnimation(fade_in_anim)
        
        # --- 总控并行组 ---
        self.master_timeline = QParallelAnimationGroup(self)
        self.master_timeline.addAnimation(size_anim)        
        self.master_timeline.addAnimation(opacity_timeline) 
        
        self.master_timeline.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainShellWindow()
    window.show()
    sys.exit(app.exec())