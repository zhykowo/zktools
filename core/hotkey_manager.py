import threading
from pynput import keyboard

class HotkeyManager:
    def __init__(self):
        self._hotkeys = {}       # 存储快捷键 { "ctrl+alt+a": callback }
        self._current_keys = set() # 记录当前被按下的键
        self._listener = None    
        self._lock = threading.Lock()

        # 建立一个修饰键的别名映射，方便用户编写规范的键名
        self._modifier_map = {
            'ctrl': ['ctrl', 'ctrl_l', 'ctrl_r'],
            'alt': ['alt', 'alt_l', 'alt_gr'],
            'shift': ['shift', 'shift_l', 'shift_r'],
            'cmd': ['cmd', 'cmd_l', 'cmd_r', 'win', 'win_l', 'win_r']
        }

    def _parse_key(self, key):
        """准确解析按键名称，防止修饰键污染"""
        if isinstance(key, keyboard.Key):
            return key.name
        elif hasattr(key, 'char') and key.char is not None:
            return key.char.lower()
        # 如果是特殊控制字符，尝试获取它的虚拟键值映射（比如 windows 下的 vk）
        elif hasattr(key, 'vk') and key.vk is not None:
            # 将虚拟键码转换为对应的小写英文字母
            if 65 <= key.vk <= 90: # A-Z
                return chr(key.vk).lower()
        return str(key).strip("'")

    def _on_press(self, key):
        """按下按键时的事件响应"""
        with self._lock:
            # 使用 listener.canonical 将被 Ctrl 污染的按键还原为原始物理按键
            if self._listener:
                canonical_key = self._listener.canonical(key)
            else:
                canonical_key = key
                
            key_name = self._parse_key(canonical_key)
            if not key_name:
                return

            self._current_keys.add(key_name)
            
            # 检查是否匹配快捷键
            for hotkey_str, callback in self._hotkeys.items():
                required_keys = hotkey_str.split('+')
                
                # 智能匹配：只要 required_keys 中的每一个键都在当前按下的键里，就认为匹配
                match = True
                for req in required_keys:
                    # 如果是修饰键，判断其左右任意一个是否被按下
                    if req in self._modifier_map:
                        if not any(mod in self._current_keys for mod in self._modifier_map[req]):
                            match = False
                            break
                    else:
                        if req not in self._current_keys:
                            match = False
                            break
                
                if match:
                    # 异步执行回调，防止阻塞
                    threading.Thread(target=callback, daemon=True).start()

    def _on_release(self, key):
        """释放按键时的事件响应"""
        with self._lock:
            if self._listener:
                canonical_key = self._listener.canonical(key)
            else:
                canonical_key = key
                
            key_name = self._parse_key(canonical_key)
            
            # 释放时，如果该键在当前按下集合里，移出它
            if key_name in self._current_keys:
                self._current_keys.remove(key_name)
            
            # 兜底清理：如果释放的是修饰键，把它所有的左右别名都清掉，防止按键粘连
            for mod_abstract, aliases in self._modifier_map.items():
                if key_name in aliases:
                    for alias in aliases:
                        self._current_keys.discard(alias)

    def register(self, hotkey_str: str, callback):
        """动态注册快捷键（如 'ctrl+alt+a'）"""
        formatted_hotkey = hotkey_str.lower().replace(' ', '')
        with self._lock:
            self._hotkeys[formatted_hotkey] = callback
        print(f"[HotkeyManager] 已成功注册快捷键: {formatted_hotkey}")

    def unregister(self, hotkey_str: str):
        """动态删除快捷键"""
        formatted_hotkey = hotkey_str.lower().replace(' ', '')
        with self._lock:
            if formatted_hotkey in self._hotkeys:
                del self._hotkeys[formatted_hotkey]
                print(f"[HotkeyManager] 已删除快捷键: {formatted_hotkey}")

    def start(self):
        """非阻塞启动"""
        if self._listener and self._listener.running:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            daemon=True
        )
        self._listener.start()
        print("[HotkeyManager] 异步监听已全面启动...")

    def stop(self):
        """停止监听"""
        if self._listener:
            self._listener.stop()
            self._listener.join()
        with self._lock:
            self._hotkeys.clear()
            self._current_keys.clear()
        print("[HotkeyManager] 监听已安全停止。")

hotkey_manager = HotkeyManager()