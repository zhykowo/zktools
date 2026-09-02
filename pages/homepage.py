from utils.drag_drop_mixin import DragDropMixin
from pages.base_page import BasePage

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QLabel

from widgets.svg_button import SvgButton
from core.page_router import page_router

from resources.svgs import settings_icon, app_center_icon
from core.colors import WHITE, COLOR_TRANSPARENT, NEUTRAL_4, to_qss_color

# 拖拽提示样式（颜色统一由 colors.py 管理）
_DROP_HINT_IDLE_QSS = (
    f"color: {to_qss_color(COLOR_TRANSPARENT)}; font-size: 18px; "
    f"border: 2px dashed {to_qss_color(NEUTRAL_4)}; border-radius: 5px; "
)
_DROP_HINT_ACTIVE_QSS = (
    f"color: {to_qss_color(WHITE)}; font-size: 18px; "
    f"border: 2px dashed {to_qss_color(NEUTRAL_4)}; border-radius: 5px; "
)

class OnDragEvent(QObject):
    on_drag_event = Signal(bool)

on_drag_bus = OnDragEvent()

class HomePage(DragDropMixin, BasePage):
    PAGE_NAME = "home"
    TITLE = "Home"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_drag_drop()

        self.target_size = (140, 50)

        layout = self.set_main_layout('h')
        assert layout is not None

        # 设置按钮 (齿轮)
        setting_btn = SvgButton(size=36, icon_size=22, svg_data=settings_icon, enable_rotation=True)
        setting_btn.clicked.connect(lambda: page_router.immediate_switch("setting"))

        app_center_btn = SvgButton(size=36, icon_size=22, svg_data=app_center_icon, enable_rotation=True)
        app_center_btn.clicked.connect(lambda: page_router.immediate_switch("module_center"))

        self.drop_hint_label = QLabel("Drag here", self)
        self.drop_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint_label.setStyleSheet(_DROP_HINT_IDLE_QSS)

        self.drop_hint_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.drop_hint_label.setMaximumWidth(0) 

        layout.addWidget(setting_btn)
        layout.addWidget(app_center_btn)
        layout.addWidget(self.drop_hint_label)

        self.drop_anim = QPropertyAnimation(self.drop_hint_label, b"maximumWidth")
        self.drop_anim.setDuration(800)
        self.drop_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

    def on_drag_enter(self):
        self.drop_hint_label.setStyleSheet(_DROP_HINT_ACTIVE_QSS)

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