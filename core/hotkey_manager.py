import ctypes
import ctypes.wintypes
import logging

logger = logging.getLogger(__name__)
import sys
import traceback

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

# Win32 常量定义
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # 防止长按按键时触发大量重复回调

WM_HOTKEY = 0x0312

# 在常量定义区域补充 Win32 虚拟键码与 KEYUP 标志
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt 键
VK_LWIN = 0x5B  # Left Win
VK_RWIN = 0x5C  # Right Win

KEYEVENTF_KEYUP = 0x0002


class HotkeyManager(QAbstractNativeEventFilter):
    """
    基于 Windows 原生 RegisterHotKey 的热键管理器（Qt 事件循环版）。

    通过 QAbstractNativeEventFilter 挂到 Qt 事件循环上拦截 WM_HOTKEY，
    不再自建消息循环线程：注册/注销直接同步执行，回调在 Qt 事件循环
    线程（主线程）内分发。

    线程模型约束：
    - register() 必须在 Qt 主线程调用（WM_HOTKEY 只投递到注册线程的消息队列）；
    - 回调在 Qt 事件循环线程同步执行，只应做轻量状态裁决并发射信号，
      不得阻塞 UI，也不得直接触碰 UI 控件。
    """

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError(
                "HotkeyManager 仅支持 Windows（依赖 RegisterHotKey / 原生消息循环）"
            )
        super().__init__()

        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

        self._hotkeys = {}  # { formatted_hotkey: hotkey_id }
        self._id_map = {}  # { hotkey_id: (formatted_hotkey, callback) }
        self._counter = 1
        self._app_id = self.kernel32.GetCurrentProcessId()
        self._atom_ids = set()  # 记录由 GlobalAddAtom 分配的全局原子 ID（注销时需释放）
        self._installed = False

        # 常用特殊按键的虚拟键码 (VK Code) 映射
        self._vk_map = {
            "space": 0x20,
            "enter": 0x0D,
            "return": 0x0D,
            "tab": 0x09,
            "esc": 0x1B,
            "escape": 0x1B,
            "backspace": 0x08,
            "delete": 0x2E,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
            "insert": 0x2D,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pagedown": 0x22,
            # 符号键 → VK 码（不能直接用 ASCII，否则会错位成其他按键，如 '.' → VK_DELETE）
            ".": 0xBE,
            ",": 0xBC,
            "/": 0xBF,
            ";": 0xBA,
            "'": 0xDE,
            "[": 0xDB,
            "]": 0xDD,
            "-": 0xBD,
            "=": 0xBB,
            "`": 0xC0,
            "\\": 0xDC,
            **{f"f{i}": 0x70 + i - 1 for i in range(1, 25)},  # F1 - F24
        }

    def _parse_hotkey_str(self, hotkey_str: str):
        """解析快捷键字符串（如 'ctrl+alt+a'），转换为 Win32 的修饰键和 VK 码"""
        parts = hotkey_str.lower().replace(" ", "").split("+")
        mods = MOD_NOREPEAT  # 默认加上防重复触发
        vk = None

        for part in parts:
            if not part:
                continue  # 容忍 'ctrl++a' 之类的空段
            if part in ("ctrl", "control"):
                mods |= MOD_CONTROL
            elif part == "alt":
                mods |= MOD_ALT
            elif part == "shift":
                mods |= MOD_SHIFT
            elif part in ("win", "cmd"):
                mods |= MOD_WIN
            elif part in self._vk_map:
                if vk is not None:
                    raise ValueError(f"快捷键 '{hotkey_str}' 包含多个主按键: {part}")
                vk = self._vk_map[part]
            elif len(part) == 1 and part.isalnum():
                if vk is not None:
                    raise ValueError(f"快捷键 '{hotkey_str}' 包含多个主按键: {part}")
                # 字母或数字的 ASCII 码与其 VK 码一致
                vk = ord(part.upper())
            else:
                raise ValueError(f"无法识别的按键名称: {part}")

        if vk is None:
            raise ValueError(f"快捷键 '{hotkey_str}' 缺少主按键！")

        return mods, vk

    def _alloc_hotkey_id(self):
        """
        分配系统级热键 ID。
        优先通过 GlobalAddAtom 生成全局唯一的原子 ID，避免与其他进程注册的
        RegisterHotKey ID 冲突（WM_HOTKEY 的 wParam 是按 ID 全局匹配的）。
        """
        name = f"PyDiHotkey_{self._app_id}_{self._counter}"
        self._counter += 1
        atom = self.kernel32.GlobalAddAtomW(name)
        if atom != 0:
            self._atom_ids.add(atom)
            return atom
        # 原子表已满等异常情况：退回进程内自增 ID（仍有极小概率与其他进程冲突）
        return self._counter - 1

    def _free_hotkey_id(self, hotkey_id):
        """释放 GlobalAddAtom 分配的原子 ID"""
        if hotkey_id in self._atom_ids:
            self.kernel32.GlobalDeleteAtom(hotkey_id)
            self._atom_ids.discard(hotkey_id)

    def _release_all_modifiers(self):
        """
        [底层通用状态清理]
        在任何热键触发时自动调用，向系统广播所有修饰键的抬起事件，
        确保后续顶层应用执行任何按键模拟时，系统上下文都是绝对干净的。
        """
        for vk in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN):
            self.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def nativeEventFilter(self, eventType, message) -> bool:
        """Qt 事件循环回调：拦截 WM_HOTKEY 并分发回调（保持 False 不吞消息）"""
        if eventType != b"windows_generic_MSG":
            return False

        try:
            ptr = message[0] if isinstance(message, tuple) else message
            msg = ctypes.wintypes.MSG.from_address(int(ptr))
        except Exception:
            return False

        if msg.message != WM_HOTKEY:
            return False

        # 1. 通用处理：触发任何快捷键前，先自动重置/释放所有修饰键状态
        self._release_all_modifiers()

        # 2. 分发回调（在主线程同步执行，回调内只做轻量裁决并发射信号）
        hotkey_id = int(msg.wParam)
        if hotkey_id in self._id_map:
            _, callback = self._id_map[hotkey_id]
            try:
                callback()
            except Exception:
                traceback.print_exc()
        return False

    # ================= 公开 API =================

    def register(self, hotkey_str: str, callback) -> bool:
        """
        动态注册快捷键（如 'ctrl+alt+a'），注册成功后将自动独占拦截。
        必须在 Qt 主线程调用；同步返回注册结果：
        True 成功；False 失败（未启动 / 解析失败 / 已被占用）。
        """
        if not self._installed:
            logger.error(
                f"[HotkeyManager] register 失败：监听未启动，请先调用 start()（快捷键 '{hotkey_str}'）"
            )
            return False

        formatted_hotkey = hotkey_str.lower().replace(" ", "")
        try:
            mods, vk = self._parse_hotkey_str(formatted_hotkey)
        except ValueError as e:
            logger.error(f"[HotkeyManager] 解析快捷键 '{hotkey_str}' 失败: {e}")
            return False

        if formatted_hotkey in self._hotkeys:
            logger.info(
                f"[HotkeyManager] 快捷键 '{hotkey_str}' 已注册，请先注销再重新注册"
            )
            return False

        hotkey_id = self._alloc_hotkey_id()
        # 注册热键（系统级独占拦截）
        if self.user32.RegisterHotKey(None, hotkey_id, mods, vk):
            self._hotkeys[formatted_hotkey] = hotkey_id
            self._id_map[hotkey_id] = (formatted_hotkey, callback)
            logger.info(
                f"[HotkeyManager] 已成功注册并独占拦截快捷键: {formatted_hotkey}"
            )
            return True
        else:
            self._free_hotkey_id(hotkey_id)
            logger.error(
                f"[HotkeyManager] 快捷键 {formatted_hotkey} 注册失败，可能已被系统或其他软件占用！"
            )
            return False

    def unregister(self, hotkey_str: str):
        """动态删除快捷键"""
        formatted_hotkey = hotkey_str.lower().replace(" ", "")
        hotkey_id = self._hotkeys.pop(formatted_hotkey, None)
        if hotkey_id is not None:
            self._id_map.pop(hotkey_id, None)
            self.user32.UnregisterHotKey(None, hotkey_id)
            self._free_hotkey_id(hotkey_id)
            logger.info(f"[HotkeyManager] 已注销快捷键: {formatted_hotkey}")

    def start(self):
        """将热键监听挂到 Qt 事件循环上（幂等）"""
        if self._installed:
            return
        app = QCoreApplication.instance()
        if app is None:
            logger.critical(
                "[HotkeyManager] start 失败：尚未创建 QCoreApplication/QApplication"
            )
            return
        app.installNativeEventFilter(self)
        self._installed = True
        logger.info("[HotkeyManager] 原生独占热键监听已挂载到 Qt 事件循环...")

    def stop(self):
        """停止监听并注销所有快捷键"""
        if not self._installed:
            return
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
        self._installed = False
        # 注销所有已注册的热键并释放原子 ID
        for hotkey_id in list(self._id_map.keys()):
            self.user32.UnregisterHotKey(None, hotkey_id)
            self._free_hotkey_id(hotkey_id)
        self._id_map.clear()
        self._hotkeys.clear()
        logger.info("[HotkeyManager] 监听已安全停止。")


# 单例导出
hotkey_manager = HotkeyManager()
