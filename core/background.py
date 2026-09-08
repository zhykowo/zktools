# background.py
"""五色光斑背景：主容器内的动态氛围光。

实现要点（对应原 TODO）：
1. 五个光斑颜色全部由 core.colors.get_accent_color(strength) 生成，
   从暗到亮取五个强度，系统强调色变化时自动刷新；
2. 光斑绘制参考 test.py：QRadialGradient 中心不透明 → 边缘全透明，
   无边框椭圆叠加。最暗的光斑最大、最先绘制（图层最靠后）；
   最亮的光斑最小、最后绘制（图层最靠前）；
3. home / module_center 页面：五个光斑重合并平滑跟随鼠标（缓动系数不同，
   移动时形成拖尾，静止时完全重合）；
4. 其他页面：五个光斑散开在中心周围，并围绕中心点匀速公转。

用法（main.py）：
    self.background = BackgroundWidget.attach_to(self.main_container)
    # 容器圆角变化时同步：self.background.set_radius(radius)
"""

import logging
import math

from PySide6.QtCore import (
    QElapsedTimer,
    QEvent,
    QPointF,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from core.colors import color_manager, get_accent_color
from core.page_router import page_router
from core.signal import global_signals

logger = logging.getLogger(__name__)

# ---- 光斑重合并跟随鼠标的页面（PAGE_NAME）----
# 使用字符串避免 core 反向依赖 pages 包
FOLLOW_PAGES = frozenset({"home", "module_center"})

# ---- 动画参数 ----
FRAME_INTERVAL_MS = 33  # 约 30fps
ROTATE_SPEED = 12.0  # 散开时的公转角速度（度/秒）
MAX_DELTA = 0.1  # 单帧最大时间步长（秒），防止卡顿后位置大跳
BREATH_AMPLITUDE = 0.07  # 公转半径的呼吸振幅
BREATH_SPEED = 0.6  # 呼吸角频率（弧度/秒）

# ---- 五个光斑的静态属性：(强调色强度, 基准半径, 中心 alpha, 跟随缓动系数) ----
# 列表顺序 = 绘制顺序：从最暗（最大、最靠后）到最亮（最小、最靠前）
SPOT_SPECS = (
    (-0.45, 250.0, 10, 0.08),
    (-0.22, 200.0, 20, 0.10),
    (0.00, 150.0, 30, 0.13),
    (0.25, 100.0, 40, 0.16),
    (0.50, 50.0, 50, 0.20),
)

# 散开时各光斑的公转半径系数（相对容器长边）：暗的大圈、亮的小圈
ORBIT_RATIOS = (0.1, 0.2, 0.3, 0.4, 0.5)

# 半径缩放基准：按容器 (w + h) / BASE_SIZE 缩放，适配不同页面尺寸
BASE_SIZE = 600.0
MIN_SCALE, MAX_SCALE = 0.35, 1.25

# 裁剪内缩量：避开主容器的描边，避免光斑盖住边框
CLIP_INSET = 1.0


class GradientSpot:
    """单个光斑：颜色与半径由 SPOT_SPECS 决定，位置逐帧缓动更新"""

    def __init__(self, strength: float, base_radius: float, alpha: int, ease: float):
        self.strength = strength  # 强调色强度（<0 变暗，>0 变亮）
        self.base_radius = base_radius  # 基准半径（实际半径再乘容器缩放比）
        self.alpha = alpha  # 光斑中心透明度
        self.ease = ease  # 60fps 下每帧趋近目标的比例
        self.color = QColor()
        self.pos = QPointF()  # 当前中心坐标（相对本控件）
        self.placed = False  # 首次定位标记（直接落位，避免从 (0,0) 飞入）

    def refresh_color(self):
        color = get_accent_color(self.strength)
        color.setAlpha(self.alpha)
        self.color = color

    def step_to(self, target: QPointF, dt: float):
        """向目标位置缓动一步；dt 为距上一帧的秒数"""
        if not self.placed:
            self.pos = QPointF(target)
            self.placed = True
            return
        # 与帧率无关的指数缓动：k = 1 - (1 - ease) ^ (dt * 60)
        k = 1.0 - (1.0 - self.ease) ** (dt * 60.0)
        self.pos.setX(self.pos.x() + (target.x() - self.pos.x()) * k)
        self.pos.setY(self.pos.y() + (target.y() - self.pos.y()) * k)


class BackgroundWidget(QWidget):
    """绘制五色光斑背景的自定义控件。

    作为主容器的子控件置底（lower()），因此绘制在容器圆角底色之上、
    页面内容之下；绘制区域裁剪为容器圆角，不遮挡边框。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 纯装饰层：不接收任何鼠标事件，避免挡住页面交互
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._host: QWidget | None = None
        self._radius = 25.0  # 与主容器同步的圆角半径
        self._scale = 1.0  # 半径随容器尺寸的缩放比
        self._angle = 0.0  # 散开时公转累计角度（度）
        self._elapsed_time = 0.0  # 累计运行时间（秒），用于呼吸效果

        self._spots = [GradientSpot(*spec) for spec in SPOT_SPECS]
        self.refresh_colors()

        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        # 帧循环的开关条件：必须同时满足「可见」与「窗口处于焦点」，
        # 任一不满足都停止定时器，避免无谓的 CPU / GPU 开销
        self._visible = False
        self._active = False

        # 系统强调色变化时自动重取五个光斑颜色
        color_manager.accent_color_changed.connect(self.refresh_colors)
        # 主窗口失焦（main.py changeEvent 广播）时暂停帧，重新聚焦时恢复
        global_signals.window_active_changed.connect(self._on_window_active_changed)

    # ---------- 装配 ----------
    @classmethod
    def attach_to(cls, host: QWidget) -> "BackgroundWidget":
        """挂到主容器上：跟随其尺寸变化，并置于所有兄弟控件最底层"""
        bg = cls(host)
        bg._host = host
        host.installEventFilter(bg)
        bg._sync_geometry()
        bg.lower()  # 置底：只覆盖容器底色，不覆盖页面内容
        bg._visible = host.isVisible()
        bg._sync_running()
        return bg

    def _sync_geometry(self):
        if self._host is None:
            return
        self.setGeometry(self._host.rect())
        w, h = self.width(), self.height()
        if w > 0 and h > 0:
            self._scale = min(MAX_SCALE, max(MIN_SCALE, (w + h) / BASE_SIZE))

    def eventFilter(self, watched, event):
        """主容器尺寸动画期间实时同步几何与缩放"""
        if watched is self._host and event.type() == QEvent.Type.Resize:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def set_radius(self, radius: float):
        """与主容器圆角保持同步，保证裁剪边界一致"""
        self._radius = float(radius)
        self.update()

    def refresh_colors(self):
        """（重新）获取五个强度的强调色"""
        for spot in self._spots:
            spot.refresh_color()
        self.update()

    # ---------- 生命周期 ----------
    def showEvent(self, event):
        super().showEvent(event)
        self._visible = True
        self._sync_running()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._visible = False
        self._sync_running()

    def _on_window_active_changed(self, is_active: bool):
        """窗口焦点变化（由 main.py 的 changeEvent 广播）：决定是否继续跑帧"""
        self._active = bool(is_active)
        self._sync_running()

    def _sync_running(self):
        """只有「可见且窗口有焦点」时才驱动帧循环"""
        self._set_running(self._visible and self._active)

    def _set_running(self, running: bool):
        if running == self._timer.isActive():
            return
        if running:
            self._clock.restart()
            self._timer.start()
        else:
            self._timer.stop()

    # ---------- 每帧更新 ----------
    def _tick(self):
        dt = min(self._clock.restart() / 1000.0, MAX_DELTA)
        self._elapsed_time += dt
        self._angle = (self._angle + ROTATE_SPEED * dt) % 360.0

        follow = self._in_follow_mode()
        for index, spot in enumerate(self._spots):
            target = self._mouse_pos() if follow else self._orbit_pos(index)
            spot.step_to(target, dt)

        self.update()

    def _in_follow_mode(self) -> bool:
        """当前页（队列队首）是否属于「重合并跟随鼠标」的页面"""
        queue = page_router.page_queue
        current = queue[0] if queue else "home"
        return current in FOLLOW_PAGES

    def _mouse_pos(self) -> QPointF:
        """鼠标在本控件内的坐标（超出边界则贴边，保证光斑不跑出容器）"""
        pos = self.mapFromGlobal(QCursor.pos())
        rect = self.rect()
        return QPointF(
            min(max(pos.x(), rect.left()), rect.right()),
            min(max(pos.y(), rect.top()), rect.bottom()),
        )

    def _orbit_pos(self, index: int) -> QPointF:
        """散开模式下第 index 个光斑的公转坐标（围绕中心点旋转）"""
        count = len(self._spots)
        long_side = max(self.width(), self.height())
        orbit = ORBIT_RATIOS[index] * long_side
        orbit *= 1.0 + BREATH_AMPLITUDE * math.sin(
            self._elapsed_time * BREATH_SPEED + index
        )

        angle = math.radians(self._angle + index * (360.0 / count))
        center = QPointF(self.rect().center())
        return QPointF(
            center.x() + math.cos(angle) * orbit,
            center.y() + math.sin(angle) * orbit,
        )

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # 裁剪进主容器圆角内部（内缩以避开描边）
        rect = QRectF(self.rect()).adjusted(
            CLIP_INSET, CLIP_INSET, -CLIP_INSET, -CLIP_INSET
        )
        radius = max(0.0, self._radius - CLIP_INSET)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)

        # 按列表顺序绘制：先大且暗（靠后），后小且亮（靠前）
        for spot in self._spots:
            radius = spot.base_radius * self._scale
            if radius <= 0:
                continue

            gradient = QRadialGradient(spot.pos, radius)
            outer_color = QColor(spot.color)
            outer_color.setAlpha(0)  # 边缘与中心同色但全透明，形成渐隐
            gradient.setColorAt(0.0, spot.color)
            gradient.setColorAt(1.0, outer_color)

            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(spot.pos, radius, radius)
