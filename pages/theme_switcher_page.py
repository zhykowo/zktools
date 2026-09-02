"""自动主题切换模块：按预设时间表自动切换 Windows 主题。

模块职责：
- 无独立界面（继承 VirtualPage "假页面"），模块中心卡片显示
  "AutoTheme On" / "AutoTheme Off"，点击切换启用/禁用；
- 仅在【软件启动】、【工作区解锁】、【预设定时点到达】时触发检查；
- 切换前读取本地 json 记录，若与目标主题一致则跳过，否则调用 ThemeSwitcher.exe 切换并记录；
- 切换消息统一走全局通知页 notify() 弹出。
"""

import bisect
import ctypes
import ctypes.wintypes
import json
import logging

logger = logging.getLogger(__name__)
import subprocess
import sys
import threading
from datetime import datetime, time, timedelta

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QWidget

# Windows 消息监听依赖
# ctypes 已在文件顶部统一导入
from pages.notify_page import VirtualPage, notify
from resources.constants import CONFIG, root_dir
from resources.svgs import theme_icon

_TOOL_PATH = root_dir / "tools" / "ThemeSwitcher.exe"
_STATE_FILE = root_dir / "data" / "theme_state.json"

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


def _apply_theme(theme_file: str) -> bool:
    """调用 ThemeSwitcher.exe 应用主题文件，返回是否成功。"""
    try:
        result = subprocess.run(
            [_TOOL_PATH, "--file", theme_file],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            logger.info(f"[ThemeSwitcher] 主题已切换: {theme_file}")
            return True
        else:
            logger.error(
                f"[ThemeSwitcher] 切换失败 (rc={result.returncode}): {result.stderr.strip()}"
            )
            return False
    except Exception as exc:
        logger.error(f"[ThemeSwitcher] 调用异常: {exc}")
        return False


class WinUnlockListener(QWidget):
    """Windows 工作区解锁监听组件（隐藏控件）"""

    unlocked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._registered = False
        if sys.platform == "win32":
            self._register_wts()

    def _register_wts(self):
        try:
            hwnd = int(self.winId())
            res = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                hwnd, NOTIFY_FOR_THIS_SESSION
            )
            if res:
                self._registered = True
        except Exception as e:
            logger.critical(f"[ThemeSwitcher] 注册工作区解锁监听失败: {e}")

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_WTSSESSION_CHANGE and msg.wParam == WTS_SESSION_UNLOCK:
                self.unlocked.emit()
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event):
        if sys.platform == "win32" and self._registered:
            try:
                hwnd = int(self.winId())
                ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            except Exception:
                raise
        super().closeEvent(event)


class ThemeSwitcherController(QObject):
    """主题切换控制器：事件触发 + 本地校验 + 后台执行"""

    state_changed = Signal(object)  # str: "on" / "off" / "switching"
    switch_finished = Signal(bool, str)  # 内部信号：(是否成功, 主题文件)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = CONFIG.get("theme_switcher", {}).get("enabled", False)
        self._is_switching = False
        self._schedule_list = []  # [(time_obj, theme_file), ...]
        self._unlock_listener = None  # 延迟初始化，见 _ensure_listener()

        self.switch_finished.connect(self._on_switch_finished)
        self._rebuild_schedule()

        # 精准定时器（非轮询，仅在需要时 setSingleShot）
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self.check_and_switch(reason="定时任务"))

        # 注意：此处不调用 QTimer.singleShot —— 它在模块 import 阶段执行，
        # 此时 QApplication 尚未创建，调用会触发
        # "QObject::startTimer: current thread's event dispatcher has already been destroyed"。
        # 相关延迟初始化已移至 init()，由 main.py 在 QApplication 创建后调用。

    def init(self):
        """QApplication 就绪后调用：完成延迟初始化（WinUnlockListener + 启动触发）"""
        self._ensure_listener()
        if self._enabled:
            QTimer.singleShot(1000, lambda: self.check_and_switch(reason="软件启动"))

    def _ensure_listener(self):
        """延迟创建 WinUnlockListener（QWidget 子类，须在 QApplication 创建后实例化）"""
        if self._unlock_listener is not None:
            return
        self._unlock_listener = WinUnlockListener()
        self._unlock_listener.unlocked.connect(
            lambda: self.check_and_switch(reason="工作区解锁")
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ---------- 本地记录管理 ----------

    def _get_recorded_theme(self) -> str:
        """从本地 json 记录中读取上次切换的主题路径"""
        if _STATE_FILE.exists():
            try:
                with open(_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_theme", "")
            except Exception as e:
                logger.error(f"[ThemeSwitcher] 读取本地状态文件异常: {e}")
        return ""

    def _record_applied_theme(self, theme_file: str):
        """记录本次切换的主题和时间到本地 json"""
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_theme": theme_file,
                "last_switch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ThemeSwitcher] 写入本地状态文件异常: {e}")

    # ---------- schedule & 时间匹配 ----------

    def _rebuild_schedule(self):
        """解析并按时间排序配置表"""
        raw = CONFIG.get("theme_switcher", {}).get("schedule", {})
        parsed = []
        for k, v in raw.items():
            parts = k.split(":")
            if len(parts) == 2:
                t_obj = time(int(parts[0]), int(parts[1]))
                parsed.append((t_obj, v))
        parsed.sort(key=lambda x: x[0])
        self._schedule_list = parsed

    def _get_target_theme(self, now: datetime) -> str:
        """根据当前时间匹配应使用的主题。

        如果早于今天所有时间点，则匹配前一天最后一个时间段的主题。
        """
        if not self._schedule_list:
            return ""
        now_time = now.time()
        times = [t for t, _ in self._schedule_list]
        pos = bisect.bisect_right(times, now_time)

        if pos == 0:
            # 早于今天第一个时间点，取列表最后一个（跨夜延续前一天最后的主题）
            return self._schedule_list[-1][1]
        return self._schedule_list[pos - 1][1]

    def _arm_next_timer(self):
        """计算距离下一个预设时间点的毫秒数并启动单次定时器"""
        self._timer.stop()
        if not self._enabled or not self._schedule_list:
            return

        now = datetime.now()
        now_time = now.time()
        times = [t for t, _ in self._schedule_list]
        pos = bisect.bisect_right(times, now_time)

        if pos < len(times):
            # 今天后续还有时间点
            next_dt = datetime.combine(now.date(), times[pos])
        else:
            # 今天的已经全部过完，取明天第一个时间点
            next_dt = datetime.combine(now.date() + timedelta(days=1), times[0])

        # 增加 1 秒缓冲，确保触发时已越过该时刻
        delta_seconds = (next_dt - now).total_seconds() + 1.0
        ms = max(1000, int(delta_seconds * 1000))

        logger.info(
            f"[ThemeSwitcher] 安排下次定时切换: {next_dt.strftime('%Y-%m-%d %H:%M:%S')} (约 {delta_seconds:.0f} 秒后)"
        )
        self._timer.start(ms)

    # ---------- 启用/禁用 ----------

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        CONFIG.setdefault("theme_switcher", {})["enabled"] = enabled

        if enabled:
            self._rebuild_schedule()
            self.check_and_switch(reason="启用模块")
        else:
            self._timer.stop()

        self.state_changed.emit("on" if enabled else "off")

    # ---------- 核心切换逻辑 ----------

    def check_and_switch(self, reason: str = "事件触发"):
        """触发入口：校验本地记录与目标主题，不一致才切换"""
        if not self._enabled:
            return

        if self._is_switching:
            logger.info(f"[ThemeSwitcher] 切换正在进行中，忽略本次触发 ({reason})")
            return

        now = datetime.now()
        target_theme = self._get_target_theme(now)
        if not target_theme:
            return

        # 检测本地历史记录
        recorded_theme = self._get_recorded_theme()
        if recorded_theme == target_theme:
            logger.info(
                f"[ThemeSwitcher] [{reason}] 目标主题与本地记录一致 ({target_theme})，跳过切换"
            )
            self._arm_next_timer()
            return

        logger.info(
            f"[ThemeSwitcher] [{reason}] 检测到主题变化，准备从 '{recorded_theme}' 切换为 '{target_theme}'"
        )
        self._is_switching = True
        self.state_changed.emit("switching")
        notify("主题切换中…", icon=theme_icon, duration=0)

        threading.Thread(
            target=self._perform_switch_worker,
            args=(target_theme,),
            daemon=True,
            name="theme-switch",
        ).start()

    def _perform_switch_worker(self, theme_file: str):
        """后台线程：调用 exe 工具，通过信号回调结果"""
        ok = _apply_theme(theme_file)
        self.switch_finished.emit(ok, theme_file)

    @Slot(bool, str)
    def _on_switch_finished(self, success: bool, theme_file: str):
        """主线程回调：更新状态并弹窗通知"""
        self._is_switching = False
        if success:
            self._record_applied_theme(theme_file)
            self.state_changed.emit("on")
            notify("主题已切换", icon=theme_icon, duration=3000)
        else:
            self.state_changed.emit("on")
            notify("主题切换失败", icon=theme_icon, duration=3000)

        # 每次切换完成（无论成功失败）后，设置下一个定时点
        self._arm_next_timer()


class ThemeSwitcherPage(VirtualPage):
    """自动主题切换模块入口：无界面"假页面"。"""

    PAGE_NAME = "theme_switcher"
    MODULE_NAME = "AutoTheme Off"
    MODULE_ICON = theme_icon

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = theme_controller
        self.controller.state_changed.connect(self._on_state_changed)

    @property
    def module_name(self) -> str:
        return "AutoTheme On" if self.controller.enabled else "AutoTheme Off"

    def on_module_center_clicked(self):
        self.controller.set_enabled(not self.controller.enabled)

    @Slot(object)
    def _on_state_changed(self, state: str):
        self.module_name_changed.emit()


# 单例初始化
theme_controller = ThemeSwitcherController()
