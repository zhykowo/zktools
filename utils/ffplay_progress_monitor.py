"""ffplay 播放进度管道监听器（单例）。

在后台守护线程上常驻一个 Named Pipe 服务端（\\\\.\\pipe\\\\ffplay_progress），
等待播放器（Rust 侧 ffplay 包装进程）接入并按行推送 JSON 进度包：

    {"video_path": "...", "current": 12.3, "duration": 95.7}

管道协议与 test.py 的演示脚本一致：BYTE 模式 + UTF-8 + 按 "\\n" 分包，
分包可能把一行 JSON 从中间截断，须缓冲重组。
本模块用 ctypes 直调 kernel32 而非 pywin32（venv 未装、Nuitka 打包更干净），
进度经 Qt 信号投递回主线程（工作线程 emit，自动走排队连接）。

用法（main.py）：

    ffplay_progress_monitor.init()   # QApplication 之后调用一次

    ffplay_progress_monitor.get().progress_updated.connect(slot)  # (video_path, current, duration)
"""

import ctypes
import json
import logging
import threading
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

PIPE_NAME = r"\\.\pipe\ffplay_progress"
BUFFER_SIZE = 4096

# ---- Win32 常量与 API 绑定 ----
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PIPE_ACCESS_INBOUND = 0x00000001  # 服务端仅接收
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 0xFF
ERROR_PIPE_CONNECTED = 535  # ConnectNamedPipe 返回失败的唯一"正常"特例：客户端抢先连上了
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
]
kernel32.CreateNamedPipeW.restype = ctypes.c_void_p
kernel32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel32.ConnectNamedPipe.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = wintypes.BOOL


class FfplayProgressMonitor(QObject):
    """管道服务端：常驻后台线程，每收到一行合法 JSON 即发一条进度信号。"""

    progress_updated = Signal(str, float, float)  # video_path, current, duration

    def start(self) -> None:
        """启动监听线程（daemon：随进程退出，无需显式停止）"""
        threading.Thread(
            target=self._serve_forever,
            daemon=True,
            name="ffplay-progress-pipe",
        ).start()

    # ---------- 服务循环 ----------
    def _serve_forever(self) -> None:
        while True:
            handle = kernel32.CreateNamedPipeW(
                PIPE_NAME,
                PIPE_ACCESS_INBOUND,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                PIPE_UNLIMITED_INSTANCES,
                BUFFER_SIZE,
                BUFFER_SIZE,
                0,
                None,
            )
            if handle is None or handle == INVALID_HANDLE_VALUE:
                logger.warning("[ffplay_progress] 创建管道失败，1s 后重试（errno=%d）", ctypes.get_last_error())
                time.sleep(1.0)
                continue

            try:
                if not kernel32.ConnectNamedPipe(handle, None) and ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                    logger.warning("[ffplay_progress] ConnectNamedPipe 失败（errno=%d），重建管道", ctypes.get_last_error())
                    continue
                logger.info("[ffplay_progress] 播放器已接入")
                self._read_loop(handle)
                logger.info("[ffplay_progress] 播放器已断开，重新等待连接")
            finally:
                kernel32.CloseHandle(handle)

    def _read_loop(self, handle: int) -> None:
        """连接存续期间持续读管道；分包缓冲，按行解析。"""
        buffer = ""
        buf = ctypes.create_string_buffer(BUFFER_SIZE)
        read = wintypes.DWORD(0)

        while True:
            ok = kernel32.ReadFile(handle, buf, BUFFER_SIZE, ctypes.byref(read), None)
            if not ok or read.value == 0:
                break  # 客户端断开（ERROR_BROKEN_PIPE）或读取失败
            buffer += buf.raw[: read.value].decode("utf-8", errors="ignore")
            buffer = self._consume_lines(buffer)

        # 断开时冲刷残留：补一个换行，处理没有结尾换行的最后一行
        if buffer.strip():
            self._consume_lines(buffer + "\n")

    def _consume_lines(self, buffer: str) -> str:
        """拆出所有完整行并解析，返回剩余的不完整尾巴。"""
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            self._emit_line(line.strip())
        return buffer

    def _emit_line(self, line: str) -> None:
        if not line:
            return
        try:
            pkg = json.loads(line)
            video_path = pkg.get("video_path") or ""
            current = float(pkg.get("current") or 0.0)
            duration = float(pkg.get("duration") or 0.0)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.debug("[ffplay_progress] 忽略无法解析的行: %r", line[:80])
            return
        if video_path:
            self.progress_updated.emit(video_path, current, duration)


_instance: FfplayProgressMonitor | None = None


def init() -> None:
    """启动管道监听（主线程调用一次；先于 FfplayProgressPage 实例化）"""
    global _instance
    if _instance is not None:
        return
    _instance = FfplayProgressMonitor()
    _instance.start()


def get() -> FfplayProgressMonitor:
    """获取监听器单例"""
    if _instance is None:
        raise RuntimeError("ffplay_progress_monitor 尚未初始化")
    return _instance


def connect_progress(slot) -> None:
    """把进度信号连接到消费者；监听器未启动时自动启动（幂等，可多次调用）"""
    if _instance is None:
        init()
    get().progress_updated.connect(slot)
