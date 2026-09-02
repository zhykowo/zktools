"""系统托盘管理器

提供系统托盘图标，作为程序的安全退出通道。
当主窗口卡死或无法正常关闭时，用户可通过托盘菜单强制退出。
"""

from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget


class SystemTrayManager:
    """管理系统托盘图标与菜单"""

    def __init__(self, window: QWidget, icon_path: str | Path | None = None):
        self.window = window

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        self._tray_icon = QSystemTrayIcon(window)

        # 设置图标
        if icon_path and Path(icon_path).exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            # 保底：使用应用图标
            self._tray_icon.setIcon(
                QApplication.style().standardIcon(
                    QApplication.style().StandardPixmap.SP_ComputerIcon
                )
            )

        self._tray_icon.setToolTip("zktools")

        # 构建右键菜单（仅保留退出功能）
        self._menu = QMenu(window)
        self._quit_action = QAction("退出", window)
        self._quit_action.triggered.connect(self._quit_app)
        self._menu.addAction(self._quit_action)
        self._tray_icon.setContextMenu(self._menu)

        # 左键单击显示窗口
        self._tray_icon.activated.connect(self._on_activated)

    def show(self):
        """显示托盘图标"""
        if self._tray_icon is not None:
            self._tray_icon.show()

    def hide(self):
        """隐藏托盘图标"""
        if self._tray_icon is not None:
            self._tray_icon.hide()

    def _show_window(self):
        """显示并激活主窗口"""
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit_app(self):
        """强制退出应用"""
        QApplication.quit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """处理托盘图标激活事件：左键单击显示窗口"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()
