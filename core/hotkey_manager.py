import ctypes
import ctypes.wintypes
import sys
import threading
import queue
import traceback

# Win32 常量定义
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # 防止长按按键时触发大量重复回调

WM_HOTKEY = 0x0312
WM_NULL = 0x0000

# 在常量定义区域补充 Win32 虚拟键码与 KEYUP 标志
VK_SHIFT   = 0x10
VK_CONTROL = 0x11
VK_MENU    = 0x12  # Alt 键
VK_LWIN    = 0x5B  # Left Win
VK_RWIN    = 0x5C  # Right Win

KEYEVENTF_KEYUP = 0x0002

# 注册/注销命令同步等待消息线程处理的默认超时（秒）
_CMD_TIMEOUT = 3.0

class HotkeyManager:
    """
    基于 Windows 原生 RegisterHotKey 的热键管理器
    对齐原本 pynput 接口，实现零成本无痛迁移 + 原生独占拦截
    """
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError("HotkeyManager 仅支持 Windows（依赖 RegisterHotKey / 原生消息循环）")

        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        
        self._hotkeys = {}       # { formatted_hotkey: (id, callback) }
        self._id_map = {}        # { id: (formatted_hotkey, callback) }
        self._counter = 1
        self._app_id = self.kernel32.GetCurrentProcessId()
        self._atom_ids = set()   # 记录由 GlobalAddAtom 分配的全局原子 ID（注销时需释放）
        
        self._cmd_queue = queue.Queue() # 线程间命令队列（用于动态注册/注销）
        self._thread = None
        self._thread_id = None
        self._running = False
        self._lock = threading.Lock()

        # 常用特殊按键的虚拟键码 (VK Code) 映射
        self._vk_map = {
            'space': 0x20, 'enter': 0x0D, 'return': 0x0D, 'tab': 0x09,
            'esc': 0x1B, 'escape': 0x1B, 'backspace': 0x08, 'delete': 0x2E,
            'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
            'insert': 0x2D, 'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
            # 符号键 → VK 码（不能直接用 ASCII，否则会错位成其他按键，如 '.' → VK_DELETE）
            '.': 0xBE, ',': 0xBC, '/': 0xBF, ';': 0xBA, "'": 0xDE,
            '[': 0xDB, ']': 0xDD, '-': 0xBD, '=': 0xBB, '`': 0xC0, '\\': 0xDC,
            **{f'f{i}': 0x70 + i - 1 for i in range(1, 25)} # F1 - F24
        }

    def _parse_hotkey_str(self, hotkey_str: str):
        """解析快捷键字符串（如 'ctrl+alt+a'），转换为 Win32 的修饰键和 VK 码"""
        parts = hotkey_str.lower().replace(' ', '').split('+')
        mods = MOD_NOREPEAT  # 默认加上防重复触发
        vk = None

        for part in parts:
            if not part:
                continue  # 容忍 'ctrl++a' 之类的空段
            if part in ('ctrl', 'control'):
                mods |= MOD_CONTROL
            elif part == 'alt':
                mods |= MOD_ALT
            elif part == 'shift':
                mods |= MOD_SHIFT
            elif part in ('win', 'cmd'):
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

    def _process_queue(self):
        """在 Windows 消息循环线程中执行注册与注销操作"""
        while not self._cmd_queue.empty():
            try:
                cmd, data = self._cmd_queue.get_nowait()
                if cmd == 'REGISTER':
                    hotkey_str, mods, vk, callback, result = data
                    hotkey_id = self._alloc_hotkey_id()

                    # 注册热键（系统级独占拦截）
                    if self.user32.RegisterHotKey(None, hotkey_id, mods, vk):
                        with self._lock:
                            self._hotkeys[hotkey_str] = hotkey_id
                            self._id_map[hotkey_id] = (hotkey_str, callback)
                        ok = True
                        print(f"[HotkeyManager] 已成功注册并独占拦截快捷键: {hotkey_str}")
                    else:
                        self._free_hotkey_id(hotkey_id)
                        ok = False
                        print(f"[HotkeyManager] 快捷键 {hotkey_str} 注册失败，可能已被系统或其他软件占用！")
                    if result is not None:
                        result.put(ok)

                elif cmd == 'UNREGISTER':
                    hotkey_str = data
                    hotkey_id = None
                    with self._lock:
                        if hotkey_str in self._hotkeys:
                            hotkey_id = self._hotkeys.pop(hotkey_str)
                            self._id_map.pop(hotkey_id, None)
                    if hotkey_id is not None:
                        self.user32.UnregisterHotKey(None, hotkey_id)
                        self._free_hotkey_id(hotkey_id)
                        print(f"[HotkeyManager] 已注销快捷键: {hotkey_str}")
            except queue.Empty:
                break
            except Exception:
                # 防止单个命令的异常（如回调异常）弄死整个消息循环
                traceback.print_exc()

    def _wake_thread(self):
        """向消息循环线程发送空消息唤醒 GetMessageW"""
        with self._lock:
            thread_id = self._thread_id
        if thread_id:
            # PostThreadMessageW 返回 0 表示失败（线程可能已退出），静默忽略
            self.user32.PostThreadMessageW(thread_id, WM_NULL, 0, 0)

    def _release_all_modifiers(self):
        """
        [底层通用状态清理]
        在任何热键触发时自动调用，向系统广播所有修饰键的抬起事件，
        确保后续顶层应用执行任何按键模拟时，系统上下文都是绝对干净的。
        """
        for vk in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN):
            self.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def _safe_dispatch(self, callback):
        """在独立线程中安全执行回调，防止异常穿透影响消息循环"""
        try:
            callback()
        except Exception:
            traceback.print_exc()

    def _msg_loop(self):
        """原生 Windows 消息循环线程"""
        with self._lock:
            self._thread_id = self.kernel32.GetCurrentThreadId()
        msg = ctypes.wintypes.MSG()

        try:
            while self._running:
                self._process_queue()

                res = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res == 0 or res == -1:
                    break

                self._process_queue()

                # 匹配到任意热键响应
                if msg.message == WM_HOTKEY:
                    # 1. 通用处理：触发任何快捷键前，先自动重置/释放所有修饰键状态
                    self._release_all_modifiers()

                    # 2. 分发回调
                    hotkey_id = int(msg.wParam)
                    if hotkey_id in self._id_map:
                        _, callback = self._id_map[hotkey_id]
                        threading.Thread(
                            target=self._safe_dispatch, args=(callback,), daemon=True
                        ).start()

                self.user32.TranslateMessage(ctypes.byref(msg))
                self.user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            # 无论正常退出还是异常，都注销所有已注册的热键
            with self._lock:
                hotkey_ids = list(self._id_map.keys())
                self._id_map.clear()
                self._hotkeys.clear()
            for hotkey_id in hotkey_ids:
                self.user32.UnregisterHotKey(None, hotkey_id)
                self._free_hotkey_id(hotkey_id)
            with self._lock:
                self._thread_id = None



    # ================= 公开 API =================

    def register(self, hotkey_str: str, callback) -> bool:
        """
        动态注册快捷键（如 'ctrl+alt+a'），注册成功后将自动独占拦截。
        同步返回注册结果：True 成功；False 失败（未启动 / 解析失败 / 已被占用）。
        """
        if not self._running:
            print(f"[HotkeyManager] register 失败：监听未启动，请先调用 start()（快捷键 '{hotkey_str}'）")
            return False

        formatted_hotkey = hotkey_str.lower().replace(' ', '')
        try:
            mods, vk = self._parse_hotkey_str(formatted_hotkey)
        except ValueError as e:
            print(f"[HotkeyManager] 解析快捷键 '{hotkey_str}' 失败: {e}")
            return False

        with self._lock:
            if formatted_hotkey in self._hotkeys:
                print(f"[HotkeyManager] 快捷键 '{hotkey_str}' 已注册，请先注销再重新注册")
                return False

        result = queue.Queue(maxsize=1)
        self._cmd_queue.put(('REGISTER', (formatted_hotkey, mods, vk, callback, result)))
        self._wake_thread()
        try:
            return bool(result.get(timeout=_CMD_TIMEOUT))
        except queue.Empty:
            print(f"[HotkeyManager] 注册快捷键 '{hotkey_str}' 超时，注册结果未知")
            return False

    def unregister(self, hotkey_str: str):
        """动态删除快捷键"""
        if not self._running:
            return
        formatted_hotkey = hotkey_str.lower().replace(' ', '')
        self._cmd_queue.put(('UNREGISTER', formatted_hotkey))
        self._wake_thread()

    def start(self):
        """非阻塞启动监听"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._msg_loop, daemon=True)
        self._thread.start()
        print("[HotkeyManager] 原生独占热键监听已启动...")

    def stop(self):
        """停止监听并注销所有快捷键"""
        if not self._running:
            return
        self._running = False
        self._wake_thread()
        if self._thread:
            self._thread.join(timeout=_CMD_TIMEOUT)
            if self._thread.is_alive():
                print("[HotkeyManager] 警告：消息线程未能在超时时间内退出，热键可能未被完全注销")
            self._thread = None
        print("[HotkeyManager] 监听已安全停止。")


# 单例导出
hotkey_manager = HotkeyManager()
