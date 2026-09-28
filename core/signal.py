"""Global Qt signals shared across modules.

Modules can import ``global_signals`` and connect to the signals
they need, avoiding circular imports and keeping the signal bus
in one place.
"""

from PySide6.QtCore import QObject, Signal


class GlobalSignalBus(QObject):
    """Singleton signal bus — one instance shared project-wide."""

    window_active_changed = Signal(bool)

    # 跨模块入口：请求翻译一段文本（由翻译模块订阅，发送方无需认识翻译模块）
    translate_shortcut = Signal(str)


global_signals = GlobalSignalBus()
