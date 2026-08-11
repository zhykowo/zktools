import ctypes
import threading
import queue

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

class HotkeyManager:
    """
    基于 Windows 原生 RegisterHotKey 的热键管理器
    对齐原本 pynput 接口，实现零成本无痛迁移 + 原生独占拦截
    """
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        
        self._hotkeys = {}       # { formatted_hotkey: (id, callback) }
        self._id_map = {}        # { id: (formatted_hotkey, callback) }
        self._counter = 1
        
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
            **{f'f{i}': 0x70 + i - 1 for i in range(1, 25)} # F1 - F24
        }

    def _parse_hotkey_str(self, hotkey_str: str):
        """解析快捷键字符串（如 'ctrl+alt+a'），转换为 Win32 的修饰键和 VK 码"""
        parts = hotkey_str.lower().replace(' ', '').split('+')
        mods = MOD_NOREPEAT  # 默认加上防重复触发
        vk = None

        for part in parts:
            if part in ('ctrl', 'control'):
                mods |= MOD_CONTROL
            elif part == 'alt':
                mods |= MOD_ALT
            elif part == 'shift':
                mods |= MOD_SHIFT
            elif part in ('win', 'cmd'):
                mods |= MOD_WIN
            elif part in self._vk_map:
                vk = self._vk_map[part]
            elif len(part) == 1:
                # 字母或数字直接取 ASCII / VK 码
                vk = ord(part.upper())
            else:
                raise ValueError(f"无法识别的按键名称: {part}")

        if vk is None:
            raise ValueError(f"快捷键 '{hotkey_str}' 缺少主按键！")

        return mods, vk

    def _process_queue(self):
        """在 Windows 消息循环线程中执行注册与注销操作"""
        while not self._cmd_queue.empty():
            try:
                cmd, data = self._cmd_queue.get_nowait()
                if cmd == 'REGISTER':
                    hotkey_str, mods, vk, callback = data
                    hotkey_id = self._counter
                    self._counter += 1
                    
                    # 注册热键（系统级独占拦截）
                    if self.user32.RegisterHotKey(None, hotkey_id, mods, vk):
                        self._hotkeys[hotkey_str] = hotkey_id
                        self._id_map[hotkey_id] = (hotkey_str, callback)
                        print(f"[HotkeyManager] 已成功注册并独占拦截快捷键: {hotkey_str}")
                    else:
                        print(f"[HotkeyManager] 快捷键 {hotkey_str} 注册失败，可能已被系统或其他软件占用！")

                elif cmd == 'UNREGISTER':
                    hotkey_str = data
                    if hotkey_str in self._hotkeys:
                        hotkey_id = self._hotkeys.pop(hotkey_str)
                        self._id_map.pop(hotkey_id, None)
                        self.user32.UnregisterHotKey(None, hotkey_id)
                        print(f"[HotkeyManager] 已注销快捷键: {hotkey_str}")
            except queue.Empty:
                break

    def _wake_thread(self):
        """向消息循环线程发送空消息唤醒 GetMessageW"""
        if self._thread_id:
            self.user32.PostThreadMessageW(self._thread_id, WM_NULL, 0, 0)

    def _release_all_modifiers(self):
        """
        [底层通用状态清理]
        在任何热键触发时自动调用，向系统广播所有修饰键的抬起事件，
        确保后续顶层应用执行任何按键模拟时，系统上下文都是绝对干净的。
        """
        for vk in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN):
            self.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def _msg_loop(self):
        """原生 Windows 消息循环线程"""
        self._thread_id = self.kernel32.GetCurrentThreadId()
        msg = ctypes.wintypes.MSG()

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
                hotkey_id = msg.wParam
                if hotkey_id in self._id_map:
                    _, callback = self._id_map[hotkey_id]
                    threading.Thread(target=callback, daemon=True).start()

            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))

        # 退出前清理注销所有已注册的热键
        for hotkey_id in list(self._id_map.keys()):
            self.user32.UnregisterHotKey(None, hotkey_id)
        self._hotkeys.clear()
        self._id_map.clear()



    # ================= 公开 API =================

    def register(self, hotkey_str: str, callback):
        """动态注册快捷键（如 'ctrl+alt+a'），注册成功后将自动独占拦截"""
        formatted_hotkey = hotkey_str.lower().replace(' ', '')
        try:
            mods, vk = self._parse_hotkey_str(formatted_hotkey)
            self._cmd_queue.put(('REGISTER', (formatted_hotkey, mods, vk, callback)))
            self._wake_thread()
        except Exception as e:
            print(f"[HotkeyManager] 解析快捷键 '{hotkey_str}' 失败: {e}")

    def unregister(self, hotkey_str: str):
        """动态删除快捷键"""
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
            self._thread.join()
        print("[HotkeyManager] 监听已安全停止。")


# 单例导出
hotkey_manager = HotkeyManager()
