"""Open file location module — VirtualPage with no UI.

Click the module center card, then click on any window to open
its executable's directory in File Explorer.  Uses the global
``window_active_changed`` signal so the capture happens the moment
zktools loses focus.
"""

import ctypes
import ctypes.wintypes
import logging
import os
import subprocess
import threading

from PySide6.QtCore import Slot

from core.signal import global_signals
from pages.notify_page import VirtualPage, notify
from resources.svgs import folder_open_icon

logger = logging.getLogger(__name__)

# Windows API helpers
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


def _get_foreground_process_path() -> str | None:
    """Return the full path of the executable owning the foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
    if not handle:
        return None

    try:
        buffer = ctypes.create_unicode_buffer(260)
        size = ctypes.wintypes.DWORD(260)
        if psapi.GetModuleFileNameExW(handle, None, buffer, size):
            return buffer.value
        return None
    finally:
        kernel32.CloseHandle(handle)


class OpenFileLocationPage(VirtualPage):
    """Open the current foreground window's file location in Explorer"""

    PAGE_NAME = "open_file_location"
    MODULE_NAME = "File Location"
    MODULE_ICON = folder_open_icon

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_capture = False
        global_signals.window_active_changed.connect(self._on_window_deactivated)

    def on_module_center_clicked(self):
        """Card click: arm capture and wait for the user to switch windows."""
        self._pending_capture = True
        notify("Click your target window…", icon=folder_open_icon, duration=0)

    @Slot(bool)
    def _on_window_deactivated(self, active: bool):
        """zktools lost focus — capture the now-foreground window."""
        if active or not self._pending_capture:
            return
        self._pending_capture = False
        threading.Thread(target=self._do_open_location, daemon=True).start()

    def _do_open_location(self):
        try:
            exe_path = _get_foreground_process_path()
            if not exe_path:
                notify("No foreground window found", icon=folder_open_icon, duration=3000)
                return

            directory = os.path.dirname(exe_path)
            logger.info(f"Opening file location: {directory}")
            subprocess.Popen(
                ["explorer", directory],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            notify(f"Success!", icon=folder_open_icon, duration=3000)
        except Exception as e:
            logger.error(f"Open file location failed: {e}")
            notify("Open failed", icon=folder_open_icon, duration=3000)
