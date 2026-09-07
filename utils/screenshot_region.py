# screenshot_region.py
"""矩形区域截图工具：全屏遮罩 + 鼠标拖拽框选，截图结果分发给其他模块。

使用方式（需在 QApplication 创建后调用）：

    from utils.screenshot_region import screenshot_region

    # 方式一：订阅信号（适合常驻监听，如热键触发）
    screenshot_region.region_selected.connect(handle_image)
    screenshot_region.capture()

    # 方式二：回调函数（一次性）
    screenshot_region.capture(callback=lambda img: img.save("shot.png"))

    # 方式三：阻塞式（适合流程式代码，如热键回调里同步取图）
    img = screenshot_region.capture_blocking()
    if img is not None:
        ...

截图对象为 QPixmap（逻辑像素尺寸），可继续传给 OCR、翻译、剪贴板等模块。
用户按 Esc 或右键取消时：方式一/二不触发回调，方式三返回 None。
"""

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import QEventLoop, QObject, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from core.colors import get_purest_accent_color

# 最小选区边长（逻辑像素）：小于此值视为误触，不产生截图
MIN_SELECT_SIZE = 5
# 遮罩暗化程度（0-255，越大越暗）
MASK_ALPHA = 120


class _RegionSelectorOverlay(QWidget):
    """全屏半透明遮罩：用户拖拽框选截图区域"""

    region_selected = Signal(object)  # QPixmap：选区截图结果
    cancelled = Signal()  # 用户取消（Esc / 右键）

    def __init__(self, background: QPixmap):
        super().__init__()
        # 背景底图：遮罩显示前已抓取全屏，避免把遮罩本身截进去
        # 注意：screen.grabWindow(0) 返回的 QPixmap 是物理像素尺寸，
        # 而遮罩几何和鼠标坐标是逻辑像素。在高 DPI 缩放（如 150% / 200%）
        # 下，直接用逻辑像素的 rect 裁剪物理像素的图片会导致选区偏移。
        # 此处将背景图缩放到逻辑像素尺寸，统一坐标系。
        dpr = background.devicePixelRatio()
        if dpr > 1.0:
            background = background.scaled(
                int(background.width() / dpr),
                int(background.height() / dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            background.setDevicePixelRatio(1.0)
        self._background = background
        self._drag_start = None  # 左键按下位置
        self._drag_end = None  # 当前拖拽位置
        self._dragging = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 覆盖全部屏幕（虚拟桌面），保证多显示器下选区坐标与背景图一致
        total = QRect()
        for screen in QApplication.screens():
            total = total.united(screen.geometry())
        self.setGeometry(total)

    # ---- 事件 ----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self._drag_end = self._drag_start
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._drag_end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._drag_end = event.position().toPoint()
        rect = self._selection_rect()
        if rect is not None and (
            rect.width() >= MIN_SELECT_SIZE and rect.height() >= MIN_SELECT_SIZE
        ):
            self._finish_and_emit(rect)
        else:
            # 选区过小（误触），视同取消
            self._cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()

    # ---- 内部 ----

    def _selection_rect(self) -> QRect | None:
        """当前选区的归一化矩形（含起点与终点像素），无选区时返回 None"""
        if self._drag_start is None or self._drag_end is None:
            return None
        # 注意：不能用 QRect(点, 点) 双点构造 + normalized()，
        # 该构造把两点当有序的 topLeft/bottomRight，反向拖拽时会偏移 1px 且少 2px。
        # 这里显式取 min/abs，保证任意方向拖拽选中的区域完全一致。
        return QRect(
            min(self._drag_start.x(), self._drag_end.x()),
            min(self._drag_start.y(), self._drag_end.y()),
            abs(self._drag_start.x() - self._drag_end.x()) + 1,
            abs(self._drag_start.y() - self._drag_end.y()) + 1,
        )

    def _finish_and_emit(self, rect: QRect):
        """结束遮罩，从背景图抠出选区部分并发出信号"""
        if self._background is None or self._background.isNull():
            logger.error("背景图无效，无法截图")
            self._cancel()
            return
        pixmap = self._background.copy(rect)
        if pixmap.isNull():
            logger.error("从背景图抠取选区失败")
            self._cancel()
            return
        self.close()
        self.deleteLater()
        self.region_selected.emit(pixmap)

    def _cancel(self):
        self.close()
        self.deleteLater()
        self.cancelled.emit()

    # ---- 绘制 ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 全屏半透明暗色遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, MASK_ALPHA))

        # 顶部提示语
        font = painter.font()
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawText(
            QRect(0, 16, self.width(), 20),
            Qt.AlignmentFlag.AlignHCenter,
            "拖拽框选截图区域，Esc / 右键取消",
        )

        rect = self._selection_rect()
        if rect is None:
            return

        # 挖空选区，露出下方真实屏幕内容
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, QBrush(Qt.BrushStyle.SolidPattern))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 选区边框（系统强调色）
        accent = get_purest_accent_color()
        painter.setPen(QPen(accent, 2))
        painter.drawRect(rect)

        # 尺寸标注：优先放在选区上方，空间不足时放在下方
        label = f"{rect.width()} × {rect.height()}"
        label_font = painter.font()
        label_font.setPixelSize(13)
        label_font.setBold(True)
        painter.setFont(label_font)
        text_y = rect.y() - 24
        if text_y < 0:
            text_y = rect.bottom() + 4
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawText(
            QRect(rect.x(), text_y, rect.width(), 20),
            Qt.AlignmentFlag.AlignRight,
            label,
        )


class ScreenshotRegionManager(QObject):
    """矩形区域截图管理器（单例）

    负责创建遮罩、收集选区截图结果，并通过信号 / 回调向外分发。
    """

    region_selected = Signal(object)  # QPixmap：选区截图
    capture_cancelled = Signal()  # 用户取消截图（Esc / 右键）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay = None  # 当前活跃的遮罩实例
        self._callback = None  # 当前截图回调

    # ---- 公开 API ----

    def capture(self, callback=None):
        """启动一次区域截图（非阻塞，结果通过信号/回调分发）。

        Args:
            callback: 可选回调函数，签名 callback(pixmap: QPixmap)。
                截图成功时调用一次；用户取消时不调用。
                未传此参数时，请订阅 region_selected 信号获取结果。
        """
        # 若已有截图流程进行中，先取消旧的
        if self._overlay is not None:
            self._overlay._cancel()

        if QApplication.instance() is None:
            raise RuntimeError(
                "screenshot_region.capture() 必须在 QApplication 创建后调用"
            )
        screen = QApplication.primaryScreen()

        if screen is None:
            logger.error("未找到可用屏幕，无法截图")
            return

        # 先抓取全屏背景（此时遮罩尚未显示，不会截进遮罩本身）
        background = screen.grabWindow(0)

        self._callback = callback
        overlay = _RegionSelectorOverlay(background)
        self._overlay = overlay
        overlay.region_selected.connect(self._on_region_selected)
        overlay.cancelled.connect(self._on_cancelled)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def capture_blocking(self):
        """阻塞式截图：用户框选完成后返回 QPixmap；取消返回 None。

        内部使用嵌套事件循环，不阻塞 Qt 事件分发，
        适合在热键回调等流程式代码中同步取图。
        """
        loop = QEventLoop()
        result = {"pixmap": None}

        def _done(pixmap):
            result["pixmap"] = pixmap
            loop.quit()

        def _cancelled():
            loop.quit()

        self.capture_cancelled.connect(_cancelled)
        try:
            self.capture(callback=_done)
            loop.exec()
        finally:
            # 避免信号在多次调用间累积
            try:
                self.capture_cancelled.disconnect(_cancelled)
            except RuntimeError:
                pass
        return result["pixmap"]

    # ---- 内部信号处理 ----

    def _on_region_selected(self, pixmap):
        self._overlay = None
        self.region_selected.emit(pixmap)
        if self._callback is not None:
            self._callback(pixmap)
            self._callback = None

    def _on_cancelled(self):
        self._overlay = None
        self._callback = None
        self.capture_cancelled.emit()


# 模块级单例：直接导入使用，无需初始化
screenshot_region = ScreenshotRegionManager()
