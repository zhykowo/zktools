import sys
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QGraphicsOpacityEffect

from utils.clipboard_monitor import ClipboardMonitor

from widgets.core_button import CoreButton
from widgets.svg_button import SvgButton

from core.page_controller import SwitchMode, page_signals
from core.window_manager import WindowManager
from core.page_animation import PageAnimationManager
from core.hotkey_manager import HotkeyManager

from pages.base_page import BasePage