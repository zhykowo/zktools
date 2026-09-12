# qr_code_page.py
"""二维码生成 / 识别页

共用一个输入框（生成与识别不再各占一个框，避免页面拥挤）：
- 识别：区域截图或选择图片 -> qr_cli decode -> 结果填进输入框
- 生成：输入框里的文本 -> qr_cli encode -> 保存成 PNG 文件

- 调用 qr_cli 都在后台线程执行，不阻塞 UI，可中途取消
- 区域截图会自动补一圈白边（Quiet Zone），缓解紧贴码边缘裁剪导致的识别失败
"""

import json
import logging
import subprocess
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QFileDialog, QHBoxLayout

from core.colors import WHITE
from pages.base_page import BasePage
from resources.constants import root_dir
from resources.svgs import qr_code_icon
from utils.screenshot_region import screenshot_region
from widgets.core_button import CoreButton
from widgets.footer_label import FooterLabel
from widgets.text_editor import RoundedTextEdit

# qr_cli decode 把结果序列化成 JSON 数组打到 stdout：
#   识别到 -> ["内容", ...]（一图多码按数组顺序）
#   没识别到 -> []
# 两种情况退出码都是 0，只有真正出错（如图片读不了）才返回非 0 并走 anyhow 的错误输出。
# 用 JSON 而非文本解析，内容里的冒号、换行、引号都不会被截断或误判。

# 截图补白：区域截图往往紧贴二维码边缘，补白后识别更稳
QUIET_ZONE_RATIO = 0.12
QUIET_ZONE_MIN_PX = 24

SAVE_FILE_FILTER = "PNG (*.png);;All Files (*)"


class QrCliWorker(QThread):
    """qr_cli 子进程基类：负责起进程 / 超时 / 取消，把原始输出交给子类解析"""

    TIMEOUT_SECONDS = 30

    def __init__(self, exe_path: Path, args: list[str], parent=None):
        super().__init__(parent)
        self._exe_path = exe_path
        self._args = args
        self._cancelled = False
        self._proc: subprocess.Popen[str] | None = None

    def cancel(self):
        """请求取消：直接终止 qr_cli 子进程，并丢弃后续结果"""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()

    def run(self):
        if self._cancelled:
            return

        try:
            proc = subprocess.Popen(
                args=[str(self._exe_path), *self._args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr，避免双管道读满阻塞
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._proc = proc
            try:
                raw = proc.communicate(timeout=self.TIMEOUT_SECONDS)[0] or ""
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                self.handle_failure(f"Timed out ({self.TIMEOUT_SECONDS}s)")
                return
        except (OSError, ValueError) as e:
            logger.exception("qr_cli 调用异常")
            self.handle_failure(str(e))
            return

        if self._cancelled:
            return

        # 只记子命令，避免把整段待编码文本打进日志
        logger.info(f"[qr_cli {self._args[0]}] exit={returncode} output={raw!r}")
        self.handle_output(returncode, raw)

    # ---------------- 子类实现 ----------------

    def handle_output(self, returncode: int, raw: str):
        raise NotImplementedError

    def handle_failure(self, message: str):
        raise NotImplementedError

    # ---------------- 工具 ----------------

    @staticmethod
    def brief(raw: str, returncode: int) -> str:
        """把 qr_cli 的多行输出压成一行简短信息"""
        text = " ".join(line.strip() for line in raw.splitlines() if line.strip())
        return text[:160] or f"Exit code: {returncode}"


class QrDecodeWorker(QrCliWorker):
    """识别图片中的二维码"""

    decode_done = Signal(list)  # 识别结果字符串列表（支持一图多码）
    decode_empty = Signal()  # 图片中未识别到二维码
    decode_error = Signal(str)  # 调用失败信息

    def __init__(self, exe_path: Path, image_path: Path, parent=None):
        super().__init__(exe_path, ["decode", str(image_path)], parent)

    def handle_failure(self, message: str):
        self.decode_error.emit(message)

    def handle_output(self, returncode: int, raw: str):
        if returncode == 0:
            results = self._parse(raw)
            if results is None:
                self.decode_error.emit(f"Unexpected output: {self.brief(raw, returncode)}")
            elif results:
                self.decode_done.emit(results)
            else:
                self.decode_empty.emit()
        else:
            self.decode_error.emit(self.brief(raw, returncode))

    @staticmethod
    def _parse(raw: str) -> list[str] | None:
        """解析 qr_cli 的 JSON 数组输出；输出不是合法 JSON 数组时返回 None"""
        # 正常只有一行 JSON，但万一混入了日志行，就从后往前找第一行以 '[' 开头的
        candidates = [raw.strip()]
        candidates.extend(line.strip() for line in reversed(raw.splitlines()) if line.strip())
        for text in candidates:
            if not text.startswith("["):
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                return [str(item) for item in data]
        return None


class QrEncodeWorker(QrCliWorker):
    """把文本编码成二维码 PNG"""

    encode_done = Signal(str)  # 生成成功，参数为输出文件路径
    encode_error = Signal(str)

    def __init__(self, exe_path: Path, text: str, output_path: Path, parent=None):
        # 参数顺序有讲究：-o 放前面、正文放 '--' 之后。
        # 否则正文以 '-' 开头时会被 clap 当成开关（如 "-hello" 命中 -h 直接打印帮助、
        # 退出码还是 0 且不生成文件），'--' 之后的第一个参数才是字面量正文。
        super().__init__(exe_path, ["encode", "-o", str(output_path), "--", text], parent)
        self._output_path = output_path

    def handle_failure(self, message: str):
        self.encode_error.emit(message)

    def handle_output(self, returncode: int, raw: str):
        if returncode != 0:
            self.encode_error.emit(self.brief(raw, returncode))
        elif self._output_path.exists():
            self.encode_done.emit(str(self._output_path))
        else:
            # 退出码 0 却没落文件：多半是参数被 clap 当成开关（见 __init__ 的说明）
            self.encode_error.emit(f"No file written: {self.brief(raw, returncode)}")


class QrCodePage(BasePage):
    """二维码页：识别（截图 / 选图）与生成（文本 -> PNG）共用一个输入框"""

    PAGE_NAME = "qr_code"
    TITLE = "QR Code"
    MODULE_NAME = "QR Code"
    MODULE_ICON = qr_code_icon

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (420, 300)

        self.qr_cli_path = root_dir / "tools" / "qr_cli" / "qr_cli.exe"
        self.scan_image_path = root_dir / "data" / "qr_scan.png"

        self._worker: QrCliWorker | None = None
        self._awaiting_capture = False  # 是否由本页发起的截图正在等待用户框选

        layout = self.set_main_layout("v")
        assert layout is not None

        # 1. 输入框：既是待生成的文本，也是识别结果的输出区
        self.text_edit = RoundedTextEdit(placeholder="Type text to generate, or scan a QR code", parent=self)
        self.text_edit.textChanged.connect(self._refresh_actions)

        # 2. 底部控制栏
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.setContentsMargins(8, 0, 8, 0)

        self.state_label = FooterLabel(parent=self)

        self.open_btn = CoreButton(text="Open")
        self.open_btn.hide()
        self.open_btn.clicked.connect(self._open_text)

        self.generate_btn = CoreButton(text="Generate")
        self.generate_btn.clicked.connect(self._generate)

        self.scan_btn = CoreButton(text="Scan", bg_color="accent")
        self.scan_btn.clicked.connect(self.capture)

        self.cancel_btn = CoreButton(text="Cancel", parent=self)
        self.cancel_btn.setBgColor("danger")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_work)

        footer.addWidget(self.state_label)
        footer.addStretch()
        footer.addWidget(self.open_btn)
        footer.addWidget(self.generate_btn)
        footer.addWidget(self.scan_btn)
        footer.addWidget(self.cancel_btn)

        layout.addWidget(self.text_edit)
        layout.addSpacing(4)
        layout.addLayout(footer)

        screenshot_region.capture_cancelled.connect(self._on_capture_cancelled)

        self._refresh_actions()

    # ==================== 输入框 ====================

    def _box_text(self) -> str:
        """输入框当前内容（生成与复制都以「看到的内容」为准）"""
        return self.text_edit.toPlainText()

    def _refresh_actions(self):
        """内容是链接时额外显示打开"""
        text = self._box_text().strip()
        has_text = bool(text)
        self.open_btn.setVisible(has_text and text.startswith(("http://", "https://")))

    def _open_text(self):
        """打开输入框里的链接（取首行，兼容一图多码的结果）"""
        text = self._box_text().strip()
        if not text:
            return
        url = text.splitlines()[0]
        webbrowser.open(url)
        logger.info(f"打开链接: {url}")

    # ==================== 生成 ====================

    def _generate(self):
        """把输入框里的文本编码成二维码，另存为 PNG"""
        text = self._box_text().strip()
        if not text:
            self._show_state("Type text first")
            self.text_edit.setFocus()
            return
        if self._worker is not None:
            return

        default_path = root_dir / "data" / "qrcode.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save QR code", str(default_path), SAVE_FILE_FILTER)
        if not path:
            return

        self._set_busy(True)
        self._show_state("Generating...")

        worker = QrEncodeWorker(self.qr_cli_path, text, Path(path), parent=self)
        worker.encode_done.connect(self._on_encode_done)
        worker.encode_error.connect(self._on_error)
        self._run_worker(worker)

    def _on_encode_done(self, output_path: str):
        self._set_busy(False)
        self._show_state(f"Saved {Path(output_path).name}")
        logger.info(f"二维码已生成: {output_path}")

    # ==================== 截图识别 ====================

    def capture(self):
        """启动区域截图；用一次性回调接收结果，避免广播给其他常驻订阅者"""
        if not self.qr_cli_path.exists():
            self._show_state("QR Cli Not Found")
            return
        self._awaiting_capture = True
        self._show_state("Waiting for selection...")
        screenshot_region.capture(callback=self._on_region_selected)

    def _on_capture_cancelled(self):
        """用户取消框选：仅当是本页发起的截图时，把状态恢复为就绪"""
        if not self._awaiting_capture:
            return
        self._awaiting_capture = False
        if not self._box_text().strip():
            self._refresh_service_state()

    def _on_region_selected(self, pixmap: QPixmap):
        """截图完成：补白边保存后开始识别"""
        self._awaiting_capture = False
        try:
            self.scan_image_path.parent.mkdir(parents=True, exist_ok=True)
            self._with_quiet_zone(pixmap).save(str(self.scan_image_path))
        except OSError, ValueError:
            logger.exception("保存截图失败")
            self._show_state("Failed to save screenshot")
            return
        logger.info(f"截图已保存: {self.scan_image_path}")
        self._start_decode(self.scan_image_path)

    def _with_quiet_zone(self, pixmap: QPixmap) -> QPixmap:
        """给截图补一圈白边

        区域截图通常紧贴二维码边缘，缺少 Quiet Zone 会直接导致识别失败，
        因此统一按短边比例补白后再交给 qr_cli。
        """
        margin = max(QUIET_ZONE_MIN_PX, int(min(pixmap.width(), pixmap.height()) * QUIET_ZONE_RATIO))
        padded = QPixmap(pixmap.width() + 2 * margin, pixmap.height() + 2 * margin)
        padded.fill(WHITE)

        painter = QPainter(padded)
        painter.drawPixmap(margin, margin, pixmap)
        painter.end()
        return padded

    # ==================== 识别 ====================

    def _start_decode(self, image_path: Path):
        """后台执行二维码识别，避免阻塞 UI"""
        if self._worker is not None:
            return  # 已有任务进行中

        logger.info(f"开始识别二维码: {image_path}")
        # 识别结果会覆盖输入框，先清空，避免失败时残留上一次的内容
        self.text_edit.setPlainText("")
        self._set_busy(True)
        self._show_state("Decoding...")

        worker = QrDecodeWorker(self.qr_cli_path, image_path, parent=self)
        worker.decode_done.connect(self._on_decode_done)
        worker.decode_empty.connect(self._on_decode_empty)
        worker.decode_error.connect(self._on_error)
        self._run_worker(worker)

    def _on_decode_done(self, results: list):
        """识别成功：内容填进输入框（多个码按行分隔，便于整体复制）"""
        self.text_edit.setPlainText("\n".join(str(item) for item in results))
        self._set_busy(False)
        self._show_state(f"{len(results)} code(s) found")
        logger.info(f"识别到 {len(results)} 个二维码")

    def _on_decode_empty(self):
        """图片中没有识别到二维码"""
        self.text_edit.setPlainText("")
        self._set_busy(False)
        self._show_state("No QR code found")

    def _on_error(self, message: str):
        """生成 / 识别出错"""
        logger.error(f"QR 操作失败: {message}")
        self._set_busy(False)
        self._show_state(message)

    # ==================== 任务调度 ====================

    def _run_worker(self, worker: QrCliWorker):
        self._worker = worker
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _set_busy(self, busy: bool):
        """执行中显示 Cancel，隐藏 Scan / Generate 并禁用选图"""
        self.scan_btn.setVisible(not busy)
        self.generate_btn.setVisible(not busy)
        self.cancel_btn.setVisible(busy)

    def _cancel_work(self):
        """取消进行中的生成 / 识别"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            worker.finished.connect(worker.deleteLater)
        self._set_busy(False)
        self._show_state("Cancelled")

    def _on_worker_finished(self):
        """后台线程自然结束（未被取消）：释放 worker"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _show_state(self, text: str):
        self.state_label.setText(text)

    # ==================== 页面生命周期 ====================

    def _refresh_service_state(self):
        """刷新 qr_cli 可用性状态（仅在输入框为空时覆盖状态文案）"""
        available = self.qr_cli_path.exists()
        self.scan_btn.setEnabled(available)
        self.generate_btn.setEnabled(available)
        if not self._box_text().strip():
            self._show_state("QR Service Ready" if available else "QR Cli Not Found")

    def on_show(self):
        """页面显示时检测 qr_cli 是否可用，动态切换 UI 状态"""
        self._refresh_service_state()

    def clear_data(self):
        # 仅在确有任务进行中时才提示 Cancelled，避免无谓覆盖状态文案
        if self._worker is not None:
            self._cancel_work()
        self.text_edit.setPlainText("")
        self._refresh_service_state()
