from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPalette, QShortcut

from core.page_router import page_router
from core.window_manager import drag_bus

from widgets.svg_button import SvgButton

from resources.svgs import arrow_left_icon, close_icon, drag_icon
from resources.colors import WHITE, COLOR_DANGER

class BasePage(QWidget):
    """所有页面的基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (300, 300)  # 默认大小，子类可以覆盖

        self.main_layout = None

        # 创建页面级 Esc 快捷键
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(page_router.exit_self)
        # 全局关闭按钮
        self.close_btn = SvgButton(self, icon_size=20, svg_data=close_icon, hover_color=COLOR_DANGER, enable_rotation=True)
        self.close_btn.clicked.connect(QApplication.instance().quit)

    def set_main_layout(self, d: str, title: str='标题占位符'):
        if d == 'v':
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 8, 0, 0)
            self.main_layout.setSpacing(8)
            self.set_header(self.main_layout, title)
            self.content_layout = QVBoxLayout()
            self.main_layout.addLayout(self.content_layout)

        elif d == 'h':
            self.main_layout = QHBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout = QHBoxLayout()
            self.main_layout.addLayout(self.content_layout)
            self.main_layout.addWidget(self.close_btn)

        return self.content_layout

    def set_header(self, main_layout: QVBoxLayout, title: str):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        # 返回按钮 + 页面标题
        header_left = QHBoxLayout()

        # 拖拽按钮 + 全局关闭按钮
        header_right = QHBoxLayout()

        title_label = QLabel(title, self)
        title_font = title_label.font()
        title_font.setPixelSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)

        title_palette = title_label.palette()
        title_palette.setColor(QPalette.ColorRole.WindowText, WHITE)
        title_label.setPalette(title_palette)

        back_btn = SvgButton(self, icon_size=20, svg_data=arrow_left_icon)
        back_btn.clicked.connect(lambda: page_router.exit_self())

        drag_btn = SvgButton(self, icon_size=20, svg_data=drag_icon)
        drag_bus.register_drag_handle_requested.emit(drag_btn)

        header_left.addWidget(back_btn)
        header_right.addWidget(drag_btn)
        header_right.addWidget(self.close_btn)
        header_left.addWidget(title_label)
        header_left.addStretch()

        header_layout.addLayout(header_left)
        header_layout.addLayout(header_right)
        main_layout.addLayout(header_layout)

    def on_show(self):
        """页面显示时调用，子类可以重写"""
        pass

    def clear_data(self):
        pass
        # print(f"🧹 已清空页面数据")

