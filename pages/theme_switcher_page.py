"""自动主题切换模块：按预设时间表自动切换 Windows 主题。

模块职责：
- 无独立界面（继承 VirtualPage "假页面"），模块中心卡片显示
  "AutoTheme On" / "AutoTheme Off"，点击切换启用/禁用；
- 启用时启动 QTimer 定时检查当前时间，按时间区间匹配最近已过
  的时间点，调用 tools/ThemeSwitcher.exe 切换主题；
- 切换消息统一走全局通知页 notify() 弹出。
"""
import bisect
import subprocess
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from pages.notify_page import VirtualPage, notify

from resources.svgs import theme_icon
from resources.constants import CONFIG, root_dir

_TOOL_PATH = root_dir / "tools" / "ThemeSwitcher.exe"


def _apply_theme(theme_file: str) -> bool:
    """调用 ThemeSwitcher.exe 应用主题文件，返回是否成功。"""
    try:
        result = subprocess.run(
            [_TOOL_PATH, "--file", theme_file],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"[ThemeSwitcher] 主题已切换: {theme_file}")
            return True
        else:
            print(f"[ThemeSwitcher] 切换失败 (rc={result.returncode}): {result.stderr.strip()}")
            return False
    except Exception as exc:
        print(f"[ThemeSwitcher] 调用异常: {exc}")
        return False


class ThemeSwitcherController(QObject):
    """主题切换控制器：状态管理 + 定时检查 + 后台执行切换"""

    # 状态变化信号（切换中/完成）
    state_changed = Signal(object)  # str: "on" / "off" / "switching"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = CONFIG.get("theme_switcher", {}).get("enabled", False)
        self._rebuild_schedule()
        self._last_slot_index = -1  # 上次切换的 slot 索引，-1 表示强制首次切换

        # 定时器：每 30 秒检查一次
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_schedule)
        if self._enabled:
            self._timer.start(30_000)

        # 启用时启动后立即按时间区间匹配切换一次
        if self._enabled:
            QTimer.singleShot(2_000, self._check_schedule)

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ---------- schedule 管理 ----------

    @staticmethod
    def _normalize_time(time_str: str) -> str:
        """标准化时间格式："7:00" → "07:00"，确保与 %H:%M 格式匹配"""
        parts = time_str.split(":")
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        return time_str

    def _rebuild_schedule(self):
        """从 CONFIG 读取 schedule，按时间排序为有序列表。"""
        raw = CONFIG.get("theme_switcher", {}).get("schedule", {})
        # [(normalized_time, theme_file), ...] 按时间升序
        self._schedule_list = sorted(
            (self._normalize_time(k), v) for k, v in raw.items()
        )

    def _find_slot_index(self, time_str: str) -> int:
        """根据当前时间找到应使用的 slot 索引。

        规则：取最后一个 <= 当前时间的 slot；
        若早于所有 slot，则取第一个（最早时间点）。
        """
        if not self._schedule_list:
            return -1
        times = [t for t, _ in self._schedule_list]
        pos = bisect.bisect_right(times, time_str)
        if pos == 0:
            return 0  # 早于第一个，视为第一个
        return pos - 1  # 最后一个 <= 当前时间的

    # ---------- 启用/禁用 ----------

    def set_enabled(self, enabled: bool):
        """启用/禁用自动切换"""
        self._enabled = enabled
        CONFIG.setdefault("theme_switcher", {})["enabled"] = enabled

        if enabled:
            self._last_slot_index = -1  # 强制立即按当前时间匹配
            self._rebuild_schedule()
            self._timer.start(30_000)
            QTimer.singleShot(1_000, self._check_schedule)
        else:
            self._timer.stop()

        self.state_changed.emit("on" if enabled else "off")

    # ---------- 切换逻辑 ----------

    def _check_schedule(self):
        """定时检查：按当前时间所属 slot 执行切换。"""
        if not self._enabled or not self._schedule_list:
            return

        now_str = datetime.now().strftime("%H:%M")
        slot_idx = self._find_slot_index(now_str)

        if slot_idx < 0:
            return
        if slot_idx == self._last_slot_index:
            return  # 仍处于同一 slot，不重复切换
        self._last_slot_index = slot_idx

        theme_file = self._schedule_list[slot_idx][1]
        # 通知 "切换中"
        self.state_changed.emit("switching")
        notify("主题切换中…", icon=theme_icon, duration=0)

        threading.Thread(
            target=self._perform_switch,
            args=(theme_file,),
            daemon=True,
            name="theme-switch",
        ).start()

    def _perform_switch(self, theme_file: str):
        """工作线程：执行切换并通知结果"""
        ok = _apply_theme(theme_file)
        if ok:
            self.state_changed.emit("on")
            notify("主题已切换", icon=theme_icon, duration=3000)
        else:
            notify("主题切换失败", icon=theme_icon, duration=3000)


class ThemeSwitcherPage(VirtualPage):
    """自动主题切换模块入口：无界面"假页面"。

    模块中心显示名由 module_name 属性动态提供
    （"AutoTheme Off" / "AutoTheme On"），点击卡片切换启用/禁用。
    """

    PAGE_NAME = "theme_switcher"
    MODULE_NAME = "AutoTheme Off"  # 兜底；实际通过 module_name 属性动态返回
    MODULE_ICON = theme_icon

    def __init__(self, parent=None):
        super().__init__(parent)

        # 使用模块级共享控制器
        self.controller = theme_controller
        self.controller.state_changed.connect(self._on_state_changed)

    @property
    def module_name(self) -> str:
        """模块中心显示名：按当前开关状态动态返回"""
        return "AutoTheme On" if self.controller.enabled else "AutoTheme Off"

    def on_module_center_clicked(self):
        """模块中心卡片点击：切换启用/禁用"""
        self.controller.set_enabled(not self.controller.enabled)

    @Slot(object)
    def _on_state_changed(self, state: str):
        """状态变化：更新模块中心卡片名称"""
        self.module_name_changed.emit()


# 模块级共享控制器单例
theme_controller = ThemeSwitcherController()