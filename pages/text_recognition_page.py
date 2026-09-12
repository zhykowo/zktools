# text_recognition_page.py
import json
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel

from core.colors import NEUTRAL_4
from pages.base_page import BasePage
from resources.constants import CONFIG, root_dir
from resources.svgs import text_scan_icon
from utils.screenshot_region import screenshot_region
from widgets.core_button import CoreButton
from widgets.selection_grid import SelectionGrid
from widgets.text_editor import RoundedTextEdit


class OcrWorker(QThread):
    """后台 OCR 识别线程

    调用 nbocr.exe 进行文字识别，完成后通过信号回传结果到主线程。
    """

    ocr_done = Signal(str)  # 识别结果文本
    ocr_error = Signal(str)  # 错误信息

    TIMEOUT_SECONDS = 300  # nbocr 最长等待时间

    PROXY_ENV_KEYS = "all_proxy"

    def __init__(self, exe_path: Path, image_path: Path, ocr_model: str, lang: str, proxy: str = "", parent=None):
        super().__init__(parent)
        self._exe_path = exe_path
        self._image_path = image_path
        self._ocr_model = ocr_model
        self._lang = lang
        self._proxy = (proxy or "").strip()
        self._cancelled = False
        self._proc: subprocess.Popen[str] | None = None

    def cancel(self):
        """请求取消：直接终止 nbocr 子进程，并丢弃后续结果"""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()

    # 已修改：nbocr 的输出（stdout + stderr）会实时转发到本项目日志，控制台可直接看到
    def run(self):
        if self._cancelled:
            return

        tmp_path = None
        proc = None
        try:
            # 使用临时文件保存 OCR 结果（比 stdout 更可靠）
            with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+", encoding="utf-8", delete=False) as tmp:
                tmp_path = tmp.name

            args = [
                str(self._exe_path),
                "r",
                str(self._image_path),
                "-d",
                str(self._ocr_model),
                "-m",
                str(self._exe_path.parent / "models"),
                "-f",
                "json",
                "-o",
                tmp_path,
            ]

            if self._lang != "Auto":
                args.extend(["-l", self._lang])

            # 为本次 nbocr 会话注入代理（模型自动下载走 proxy-from-env，国内直连基本下不动）
            env = os.environ.copy()
            if self._proxy:
                env[self.PROXY_ENV_KEYS] = self._proxy
                logger.info(f"[nbocr] 已为本次会话设置代理: {self._proxy}")

            # 流式读取：nbocr 的进度/日志实时转发到本项目 logger（控制台可见）
            proc = subprocess.Popen(
                args=args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr，避免双管道读满阻塞
                text=True,
                encoding="utf-8",
                errors="replace",  # nbocr 可能输出非 UTF-8 字节，避免解码直接崩溃
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._proc = proc

            def _pump_output():
                """把 nbocr 的每行输出实时写入本项目日志"""
                try:
                    for line in proc.stdout or ():
                        line = line.rstrip()
                        if line:
                            logger.info(f"[nbocr] {line}")
                except OSError, ValueError:
                    logger.debug("[nbocr] 输出流读取中断", exc_info=True)

            pump = threading.Thread(target=_pump_output, daemon=True)
            pump.start()

            try:
                returncode = proc.wait(timeout=self.TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.ocr_error.emit(f"OCR timed out ({self.TIMEOUT_SECONDS}s)")
                return
            finally:
                pump.join(timeout=2)  # 等输出转发收尾，避免丢掉最后几行

            if self._cancelled:
                return

            if returncode == 0:
                raw = Path(tmp_path).read_text(encoding="utf-8").strip()
                if not raw:
                    self.ocr_done.emit("(No text detected)")
                else:
                    try:
                        # JSON 输出：提取每条结果的 text 字段，按行拼接
                        data = json.loads(raw)
                        text = "\n".join(item["text"] for item in data.get("results", [])).strip()
                    except json.JSONDecodeError, KeyError, TypeError:
                        # 非 JSON 输出：直接使用原始内容
                        text = raw
                    if text:
                        self.ocr_done.emit(text)
                        logger.info(f"[nbocr] 识别完成，共 {len(text.splitlines())} 行")
                    else:
                        self.ocr_done.emit("(No text detected)")
            else:
                self.ocr_error.emit(f"Exit code: {returncode}")

        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.kill()
                proc.wait()
            self.ocr_error.emit(f"OCR timed out ({self.TIMEOUT_SECONDS}s)")
        except (OSError, ValueError) as e:
            logger.exception("OCR 识别调用异常")
            self.ocr_error.emit(str(e))
        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    logger.debug(f"清理 OCR 临时文件失败: {tmp_path}")


class TextRecognitionPage(BasePage):
    PAGE_NAME = "text_recognition"
    TITLE = "Text Recognition"
    MODULE_NAME = "OCR"
    MODULE_ICON = text_scan_icon

    SUPPORTED_LANGUAGES: ClassVar[list[str]] = [
        "Auto",
        "English",
        "Chinese",
        "Japanese",
        "Korean",
        "French",
        "German",
        "Spanish",
        "Russian",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (400, 300)

        self.screenshot_path = root_dir / "data" / "screenshot.png"
        self.ocr_script_path = root_dir / "tools" / "newbee_ocr" / "nbocr.exe"

        # 后台 OCR 线程状态
        self._worker: OcrWorker | None = None
        self._current_lang = "Auto"

        layout = self.set_main_layout("v")
        assert layout is not None

        # 1. 文本输出区域
        self.text_edit = RoundedTextEdit(placeholder="Output", parent=self)

        # 2. 语言选择网格（选中回调直接绑定 _on_lang_selected，内部 _clear 复用）
        self.selection_grid = SelectionGrid()
        self.selection_grid.item_selected.connect(lambda _: self.selection_grid.collapse())
        # 3. 底部控制栏
        footer = QHBoxLayout()

        self.lang_button = CoreButton(text=self._current_lang)
        self.lang_button.setCheckable(True)
        self.lang_button.clicked.connect(self._toggle_lang_grid)

        self.download_serve_button = CoreButton(text="Download")
        self.download_serve_button.hide()
        self.download_serve_button.clicked.connect(self._download_ocr_service)

        self.serve_state = self._make_footer_label()

        self.ocr_button = CoreButton(text="Get Text", bg_color="accent")
        self.ocr_button.clicked.connect(self.capture)

        self.cancel_btn = CoreButton("Cancel", parent=self)
        self.cancel_btn.setBgColor("danger")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_ocr)

        footer.setSpacing(8)
        footer.addWidget(self.download_serve_button)
        footer.addWidget(self.lang_button)
        footer.addWidget(self.serve_state)
        footer.addStretch()
        footer.addWidget(self.ocr_button)
        footer.addWidget(self.cancel_btn)
        footer.setContentsMargins(8, 0, 8, 0)

        # 布局组织
        layout.addWidget(self.text_edit)
        layout.addSpacing(4)
        layout.addLayout(footer)
        layout.setSpacing(8)
        layout.addWidget(self.selection_grid)

        # 截图信号连接
        screenshot_region.region_selected.connect(self.save_pixmap)

    def _make_footer_label(self) -> QLabel:
        """底部状态栏的灰色小字标签"""
        label = QLabel(self)
        label_font = label.font()
        label_font.setPixelSize(11)
        label.setFont(label_font)

        palette = label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, NEUTRAL_4)
        label.setPalette(palette)
        return label

    # ==================== 截图流程 ====================

    def capture(self):
        """启动区域截图"""
        screenshot_region.capture()

    def save_pixmap(self, pixmap):
        """保存截图并自动触发 OCR 识别"""
        # 确保截图目录存在
        self.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(self.screenshot_path))
        logger.info(f"截图已保存: {self.screenshot_path} (尺寸: {pixmap.width()}x{pixmap.height()})")
        self.start_recognition()

    # ==================== OCR 识别 ====================

    def start_recognition(self):
        """后台执行 OCR 识别，避免阻塞 UI"""
        if self._worker is not None:
            return  # 已有识别进行中

        logger.info(f"开始 OCR 识别: {self.screenshot_path}, 语言: {self._current_lang}")

        self._set_recognizing(True)

        nb_lang = self._current_lang

        self._worker = OcrWorker(
            exe_path=self.ocr_script_path,
            image_path=self.screenshot_path,
            ocr_model=CONFIG.get("text_recognition", {}).get("ocr_model", "v6-small"),
            lang=nb_lang,
            proxy=self._proxy_config(),
            parent=self,
        )
        self._worker.ocr_done.connect(self._on_ocr_done)
        self._worker.ocr_error.connect(self._on_ocr_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _set_recognizing(self, recognizing: bool):
        """识别中显示红色 Cancel 按钮、隐藏 Get Text 按钮"""
        self.ocr_button.setVisible(not recognizing)
        self.cancel_btn.setVisible(recognizing)

    def _cancel_ocr(self):
        """取消进行中的 OCR 识别"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            worker.finished.connect(worker.deleteLater)
        self._set_recognizing(False)

    def _on_ocr_done(self, text: str):
        """OCR 识别完成：显示结果文本"""
        self.text_edit.setText(text)
        self._set_recognizing(False)

    def _on_ocr_error(self, error_msg: str):
        """OCR 识别出错：显示错误信息"""
        logger.error(f"OCR 识别失败: {error_msg}")
        self.text_edit.setText(f"OCR Error: {error_msg}")
        self._set_recognizing(False)

    def _on_worker_finished(self):
        """后台线程自然结束（未被取消）：释放 worker"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    # ==================== 服务检测 ====================

    def _proxy_config(self) -> str:
        """从配置文件读取 OCR 代理地址（text_recognition.proxy），空串表示不设置

        每次识别都重新读取，改完 config.json 无需重启即可生效。
        """
        section = CONFIG.get("text_recognition") or {}
        return str(section.get("proxy") or "").strip()

    def on_show(self):
        """页面显示时检测 OCR 服务是否存在，动态切换 UI 状态"""
        proxy = self._proxy_config()
        proxy_state = f" · Proxy" if proxy else ""
        if self.ocr_script_path.exists():
            self.lang_button.show()
            self.download_serve_button.hide()
            self.serve_state.setText(f"OCR Service Ready{proxy_state}")
        else:
            self.lang_button.hide()
            self.download_serve_button.show()
            self.serve_state.setText(f"OCR Service Not found{proxy_state}")

    def _download_ocr_service(self):
        """下载 OCR 服务（占位实现，打开一个示例链接）"""
        import webbrowser

        url = "https://github.com/zibo-chen/newbee-ocr-cli/releases"
        webbrowser.open(url)
        logger.info(f"用户点击下载 OCR 服务: {url}")

    # ==================== 语言选择 ====================

    def _toggle_lang_grid(self):
        """展开/收起语言选择网格"""
        self.selection_grid.toggle(
            trigger_btn=self.lang_button,
            items=self.SUPPORTED_LANGUAGES,
            current_value=self._current_lang,
            callback=self._on_lang_selected,
        )

    def _on_lang_selected(self, display_name: str):
        """语言选择回调：更新当前语言并收起网格"""
        for lang in self.SUPPORTED_LANGUAGES:
            if lang == display_name:
                self._current_lang = lang
                self.lang_button.setText(lang)
                break
        # 收起网格
        self.selection_grid.collapse()

    # ==================== 页面生命周期 ====================

    def clear_data(self):
        self._cancel_ocr()
        self.text_edit.setText("")
        self.selection_grid.collapse()
