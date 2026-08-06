from utils.DragDropMixin import DragDropMixin
from pages.base_page import BasePage

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QHBoxLayout, QLabel

from widgets.SvgButton import SvgButton
from core.page_controller import page_signals

from resources.svgs import settings_icon

class OnDragEvent(QObject):
    on_drag_event = Signal(bool)

on_drag_bus = OnDragEvent()

class HomePage(DragDropMixin, BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_drag_drop()

        self.target_size = (100, 50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 设置按钮 (齿轮)
        setting_btn = SvgButton(size=30, icon_size=22, svg_data=settings_icon, hover_color="#0980ff", enable_rotation=True)
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