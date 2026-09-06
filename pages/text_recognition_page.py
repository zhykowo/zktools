import logging
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel

from core.colors import COLOR_DANGER, NEUTRAL_2, NEUTRAL_4
from pages.base_page import BasePage
from resources.constants import root_dir
from resources.svgs import text_scan_icon
from utils.screenshot_region import screenshot_region
from widgets.core_button import CoreButton
from widgets.selection_grid import SelectionGrid
from widgets.text_editor import RoundedTextEdit


class OcrWorker(QThread):
    """后台 OCR 识别线程

    调用 cli.exe 进行文字识别，完成后通过信号回传结果到主线程。
    """

    ocr_done = Signal(str)  # 识别结果文本
    ocr_error = Signal(str)  # 错误信息

    def __init__(self, exe_path: Path, image_path: Path, lang: str, parent=None):
        super().__init__(parent)
        self._exe_path = exe_path
        self._image_path = image_path
        self._lang = lang
        self._cancelled = False

    def cancel(self):
        """请求取消（同步请求无法中断网络传输，但会丢弃结果）"""
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return

        tmp_path = None
        try:
            # 使用临时文件保存 OCR 结果（比 stdout 更可靠）
            with tempfile.NamedTemporaryFile(
                suffix=".txt", mode="w+", encoding="utf-8", delete=False
            ) as tmp:
                tmp_path = tmp.name

            result = subprocess.run(
                [
                    str(self._exe_path),
                    "-i",
                    str(self._image_path),
                    "-l",
                    self._lang,
                    "-o",
                    tmp_path,
                    "--no-vis",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if self._cancelled:
                return

            if result.returncode == 0:
                text = Path(tmp_path).read_text(encoding="utf-8").strip()
                if text:
                    self.ocr_done.emit(text)
                else:
                    self.ocr_done.emit("(No text detected)")
            else:
                error_msg = result.stderr.strip() or f"Exit code: {result.returncode}"
                self.ocr_error.emit(error_msg)

        except subprocess.TimeoutExpired:
            self.ocr_error.emit("OCR timed out (30s)")
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

    # (语言代码, 显示名称)
    SUPPORTED_LANGUAGES: ClassVar[list[tuple[str, str]]] = [
        ("ch", "Chinese"),
        ("chinese_cht", "Chinese (Trad.)"),
        ("en", "English"),
        ("japan", "Japanese"),
        ("ko", "Korean"),
        ("latin", "Latin"),
        ("th", "Thai"),
        ("arabic", "Arabic"),
        ("cyrillic", "Cyrillic"),
        # ("devanagari", "Devanagari"),
    ]

    GRID_ITEM_HEIGHT = 36
    GRID_SPACING = 8

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (400, 300)

        self.screenshot_path = root_dir / "data" / "screenshot.png"
        self.ocr_script_path = root_dir / "tools" / "ocr" / "cli.exe"

        # 后台 OCR 线程状态
        self._worker: OcrWorker | None = None
        self._current_lang = "ch"
        self._current_lang_display = "Chinese"

        layout = self.set_main_layout("v")
        assert layout is not None

        # 1. 文本输出区域
        self.text_edit = RoundedTextEdit(placeholder="Output", parent=self)

        # 2. 语言选择网格（选中回调直接绑定 _on_lang_selected，内部 _clear 复用）
        self.selection_grid = SelectionGrid(self)
        self.selection_grid.configure(
            cols=3,
            item_height=self.GRID_ITEM_HEIGHT,
            spacing=self.GRID_SPACING,
            idle_bg=NEUTRAL_2,
        )

        # 3. 底部控制栏
        footer = QHBoxLayout()

        self.lang_button = CoreButton(text=self._current_lang_display)
        self.lang_button.clicked.connect(self._toggle_lang_grid)

        self.download_serve_button = CoreButton(text="Download")
        self.download_serve_button.hide()
        self.download_serve_button.clicked.connect(self._download_ocr_service)

        self.serve_state = self._make_footer_label()

        self.ocr_button = CoreButton(text="Get Text")
        self.ocr_button.clicked.connect(self.capture)

        self.cancel_btn = CoreButton("Cancel", parent=self)
        self.cancel_btn.setBgColor(COLOR_DANGER)
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_ocr)

        footer.setSpacing(8)
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
        logger.info(
            f"截图已保存: {self.screenshot_path} (尺寸: {pixmap.width()}x{pixmap.height()})"
        )
        self.start_recognition()

    # ==================== OCR 识别 ====================

    def start_recognition(self):
        """后台执行 OCR 识别，避免阻塞 UI"""
        if self._worker is not None:
            return  # 已有识别进行中

        logger.info(
            f"开始 OCR 识别: {self.screenshot_path}, 语言: {self._current_lang}"
        )

        self._set_recognizing(True)

        self._worker = OcrWorker(
            exe_path=self.ocr_script_path,
            image_path=self.screenshot_path,
            lang=self._current_lang,
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

    def on_show(self):
        """页面显示时检测 OCR 服务是否存在，动态切换 UI 状态"""
        if self.ocr_script_path.exists():
            self.lang_button.show()
            self.download_serve_button.hide()
            self.serve_state.setText("OCR Service Ready")
        else:
            self.lang_button.hide()
            self.download_serve_button.show()
            self.serve_state.setText("OCR Service Not found")

    def _download_ocr_service(self):
        """下载 OCR 服务（占位实现，打开一个示例链接）"""
        import webbrowser

        url = "https://github.com/zhykowo/quick_rapidocr/releases"
        webbrowser.open(url)
        logger.info(f"用户点击下载 OCR 服务: {url}")

    # ==================== 语言选择 ====================

    def _toggle_lang_grid(self):
        """展开/收起语言选择网格"""
        if self.selection_grid.height() > 0:
            self.selection_grid.collapse()
        else:
            # 展开（populate 内部会先清空旧按钮）
            display_names = [name for _, name in self.SUPPORTED_LANGUAGES]
            self.selection_grid.populate(
                items=display_names,
                current_value=self._current_lang_display,
                on_select_callback=self._on_lang_selected,
            )
            self.selection_grid.expand_to(len(self.SUPPORTED_LANGUAGES))

    def _on_lang_selected(self, display_name: str):
        """语言选择回调：更新当前语言并收起网格"""
        for code, name in self.SUPPORTED_LANGUAGES:
            if name == display_name:
                self._current_lang = code
                self._current_lang_display = name
                self.lang_button.setText(name)
                break
        # 收起网格
        self.selection_grid.collapse()

    # ==================== 页面生命周期 ====================

    def clear_data(self):
        self._cancel_ocr()
        self.text_edit.setText("")
        if self.selection_grid.height() > 0:
            self.selection_grid.collapse()
