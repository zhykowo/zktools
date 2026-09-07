"""Global Qt signals shared across modules.

Modules can import ``global_signals`` and connect to the signals
they need, avoiding circular imports and keeping the signal bus
in one place.
"""

from PySide6.QtCore import QObject, Signal


class GlobalSignalBus(QObject):
    """Singleton signal bus — one instance shared project-wide."""

    window_active_changed = Signal(bool)


global_signals = GlobalSignalBus()