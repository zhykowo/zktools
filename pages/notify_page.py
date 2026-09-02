"""全局通知页：所有瞬时消息提醒的统一出口，由 main.py 注册一次（全局单例）。

本模块同时提供 VirtualPage——无界面模块的 BasePage 兼容替代（"假页面"），
触摸板开关、剪贴板变化等纯后台模块继承它注册进页面池，状态展示统一走
本模块的 notify()。

其他页面/模块通过模块级 notify() 发送通知：

    from pages.notify_page import notify

    notify("Copied!", icon=clipboard_icon, duration=1500)

行为约定：
- notify() 只登记待显示内容并把本页立即切换到队首；文字/图标的真正
  应用发生在切换动画透明度暗下瞬间的 on_show()，因此消息覆盖时天然
  形成"淡出旧消息 → 淡入新消息"的过渡动画；
- 消息冲突（上一条未结束时又来一条）：新消息直接覆盖旧消息。旧消息的
  自动退出定时器在登记新消息时即被取消，不会出现旧定时器在切换动画
  期间触发、把尚未显示的新消息顶掉的竞态；
- target_size 随消息长度动态计算（PageAnimationManager.switch_to 每次
  都重新读取 target_size，允许频繁修改）；文本始终单行不换行，超宽
  时容器封顶宽度、超长部分裁掉；
- duration <= 0 表示常驻，直到被下一条消息覆盖（触摸板"切换中"状态用）；
- 消息文本由 NotifyLabel 渲染：动态行渐变（白 ↔ 强调色行波，自左向右
  扫过）+ 逐字冒出动画（启动间隔递减的加速节奏，单字时长恒定）。
"""

import math

from PySide6.QtCore import QElapsedTimer, QObject, QPointF, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.colors import WHITE, color_manager, get_accent_color
from core.page_router import page_router
from pages.base_page import BasePage
from resources.svgs import square_icon
from widgets.svg_button import SvgButton


class VirtualPage(QObject):
    """无界面模块的 BasePage 兼容替代（"假页面"）。

    BasePage 对无界面模块太重（QWidget / Esc 快捷键 / 关闭按钮 / 布局）。
    只有后台逻辑、经全局通知页展示状态的模块（触摸板开关、剪贴板变化
    等）改继承本类：仍以 PAGE_NAME 经 page_router.register_virtual() 注册
    进页面池，享受模块中心卡片（module_name / module_icon /
    on_module_center_clicked / module_name_changed 信号），但没有任何
    界面——dispatch 会拒绝把虚拟页面作为切换目标。
    """

    PAGE_NAME = None
    MODULE_NAME = None  # None/空：不显示在模块中心
    MODULE_ICON = square_icon

    # 模块中心名称变化信号：module_center_page 订阅后实时刷新卡片
    module_name_changed = Signal()

    virtual = True  # 路由层标记：无界面，不可切换显示

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = ""

    @property
    def module_name(self) -> str | None:
        """模块中心显示名；默认取类属性，子类可重写为动态值"""
        return self.MODULE_NAME

    @property
    def module_icon(self) -> str:
        """模块中心卡片图标（SVG 数据）；默认取类属性，子类可重写为动态值"""
        return self.MODULE_ICON

    def on_module_center_clicked(self):
        """模块中心卡片点击行为：默认无操作，子类按需重写"""


class NotifyLabel(QWidget):
    """通知文本控件：逐字冒出动画 + 动态行渐变，两种效果叠加互不干扰。

    - 行渐变：每行一个横跨行宽的线性渐变画笔（白色 ↔ 系统强调色的行波），
      波形相位随时间循环推进：同一位置的颜色持续变化，波峰自左向右扫过；
    - 逐字动画：所有字符共享同一时钟。第 k 个字符的启动时刻按加速曲线
      分布（相邻间隔递减，浮现节奏逐渐加快），单字动画时长恒定：
      透明度淡入 + 自下而上位移（带轻微回弹）。渐变由画笔颜色承担，
      与逐字的透明度/位移自然叠加。

    动画定时器仅在控件可见期间运行（showEvent/hideEvent 接管）。
    """

    # ---- 逐字动画参数（可按观感微调） ----
    CHAR_DURATION = 210  # 单字动画时长 ms（恒定，不随位置变化）
    DROP_PX = 10  # 单字起始向下偏移量
    BACK_OVERSHOOT = 1.2  # 位移回弹强度（标准 OutBack 为 1.0）
    ACCEL_P = 1.8  # 启动时刻曲线指数，>1 时相邻间隔递减（逐渐加快）
    SPAN_BASE = 260  # 首末字符启动间隔：基础时长 ms
    SPAN_PER_CHAR = 9  # 每个字符追加的间隔 ms
    SPAN_MIN = 320
    SPAN_MAX = 900
    LINE_SPACING = 2  # 额外行距 px

    # ---- 行渐变参数 ----
    WAVE_PERIOD = 2600  # 渐变行波循环周期 ms
    WAVE_STOPS = 12  # 每行渐变的采样档数
    WAVE_STRENGTH = 0.85  # 行波峰值处的强调色混合上限

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._text = ""
        self._chars = []  # [(起始索引, 子串), ...] 逐码点拆分
        self._layout = None  # QTextLayout（QTextLine 依附其存活，须持有）
        self._lines = []
        self._layout_width = -1

        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._wave_color = get_accent_color()
        color_manager.accent_color_changed.connect(self._on_accent_changed)

    # ---------- 公开接口 ----------
    def text(self) -> str:
        return self._text

    def set_text(self, text: str):
        """设置文本并重置逐字动画时钟（同文本重复设置也会重播动画）"""
        self._text = text.replace("\n", " ")
        self._chars = self._split_chars(self._text)
        self._lines = []  # 布局缓存失效，paint 时按当前宽度重建
        self._clock.restart()
        self._timer.start()  # 控件隐藏期间 update() 为空操作，hideEvent 会停表
        self.update()

    # ---------- 可见性接管定时器 ----------
    def showEvent(self, event):
        if self._text:
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _on_accent_changed(self, new_color: QColor):
        """系统强调色变化时更新波浪动画颜色"""
        self._wave_color = new_color
        self.update()

    # ---------- 布局 ----------
    @staticmethod
    def _split_chars(text: str) -> list[tuple[int, str]]:
        """逐码点拆分文本：(UTF-16 码元起始位置, 码点)。

        Python 按码点索引而 Qt 文本坐标（QTextLine 的 textStart/textLength/
        cursorToX）按 UTF-16 码元计数，emoji 等增补平面字符占两个码元，
        须换算后才能对上 Qt 的行内位置。
        """
        chars = []
        unit = 0
        for cp in text:
            chars.append((unit, cp))
            unit += 2 if cp > "\uffff" else 1
        return chars

    @staticmethod
    def _build_lines(text: str, width: float, font: QFont):
        """按给定宽度布局文本（不换行，单行；测量与绘制共用同一逻辑）"""
        layout = QTextLayout(text, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        layout.setTextOption(option)
        layout.beginLayout()
        lines = []
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(width, 1))
            lines.append(line)
        layout.endLayout()
        return layout, lines

    def _ensure_layout(self):
        """按控件当前宽度（重新）布局文本；文本或宽度变化时重建缓存"""
        width = max(self.width(), 1)
        if self._lines and self._layout_width == width:
            return
        self._layout, self._lines = self._build_lines(self._text, width, self.font())
        self._layout_width = width
        y = 0.0
        for line in self._lines:
            line.setPosition(QPointF(0.0, y))
            y += line.height() + self.LINE_SPACING

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        if not self._text:
            return
        self._ensure_layout()
        if not self._lines:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())

        t = self._clock.elapsed()
        phase = (t % self.WAVE_PERIOD) / self.WAVE_PERIOD

        # 文本块整体垂直居中
        total_h = sum(l.height() for l in self._lines) + self.LINE_SPACING * (
            len(self._lines) - 1
        )
        y0 = max((self.height() - total_h) / 2.0, 0.0)

        n = max(len(self._chars), 1)
        span = min(
            max(self.SPAN_BASE + self.SPAN_PER_CHAR * n, self.SPAN_MIN), self.SPAN_MAX
        )

        char_ptr = 0
        pen = QPen()
        for line in self._lines:
            line_begin = line.textStart()
            line_end = line_begin + line.textLength()
            pen.setBrush(QBrush(self._line_gradient(line.naturalTextWidth(), phase)))
            painter.setPen(pen)
            baseline = y0 + line.position().y() + line.ascent()
            # 单次顺序扫描：全部字符按文本顺序落入各自行内
            while char_ptr < len(self._chars) and self._chars[char_ptr][0] < line_end:
                start, substr = self._chars[char_ptr]
                if start >= line_begin:
                    p = self._char_progress(char_ptr, n, span, t)
                    if p > 0.0:
                        # 位移带回弹地向上冒出，透明度独立淡入
                        y_off = self.DROP_PX * (1.0 - self._out_back(p))
                        painter.setOpacity(self._out_cubic(p))
                        # 本版本 PySide6 的 cursorToX 返回 (x, edge) 元组
                        x = line.cursorToX(start)
                        if isinstance(x, tuple):
                            x = x[0]
                        painter.drawText(QPointF(x, baseline + y_off), substr)
                char_ptr += 1
        painter.setOpacity(1.0)

    # ---------- 时序与缓动 ----------
    def _char_progress(self, k: int, n: int, span: float, t: float) -> float:
        """第 k 个字符的动画进度 [0,1]。

        启动时刻 start = span * (1 - (1 - k/n)^P)：P > 1 时相邻间隔递减、
        浮现节奏逐渐加快；单字动画时长恒定为 CHAR_DURATION。
        """
        start = span * (1.0 - (1.0 - k / n) ** self.ACCEL_P)
        return max(0.0, min((t - start) / self.CHAR_DURATION, 1.0))

    @staticmethod
    def _out_cubic(p: float) -> float:
        return 1.0 - (1.0 - p) ** 3

    def _out_back(self, p: float) -> float:
        """带回弹的缓出：字符略微冒过头再落回最终位置"""
        c1 = 1.70158 * self.BACK_OVERSHOOT
        c3 = c1 + 1.0
        q = p - 1.0
        return 1.0 + c3 * q**3 + c1 * q**2

    # ---------- 渐变 ----------
    def _line_gradient(self, line_width: float, phase: float) -> QLinearGradient:
        """横跨一行宽度的动态渐变：白 ↔ 强调色行波，相位随时间自左向右扫过"""
        grad = QLinearGradient(0.0, 0.0, max(line_width, 1.0), 0.0)
        accent = self._wave_color
        for s in range(self.WAVE_STOPS + 1):
            u = s / self.WAVE_STOPS
            wave = (
                0.5 - 0.5 * math.cos(2.0 * math.pi * (u - phase))
            ) * self.WAVE_STRENGTH
            grad.setColorAt(
                u,
                QColor(
                    round(WHITE.red() + (accent.red() - WHITE.red()) * wave),
                    round(WHITE.green() + (accent.green() - WHITE.green()) * wave),
                    round(WHITE.blue() + (accent.blue() - WHITE.blue()) * wave),
                ),
            )
        return grad


class NotifyPage(BasePage):
    """通知页（瞬时消息页）：仅经 notify() 驱动显示，不出现在模块中心"""

    PAGE_NAME = "notify"
    TITLE = "Notify"

    MAX_WIDTH = 430  # 主窗口 450 - 容器左右边距 10 * 2
    MIN_WIDTH = 160
    BASE_HEIGHT = 50  # 单行消息高度，与旧 clipboard/touchpad 通知尺寸一致

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (self.MIN_WIDTH, self.BASE_HEIGHT)

        layout = self.set_main_layout("h")
        assert self.main_layout is not None
        assert layout is not None
        self.main_layout.setSpacing(6)
        layout.setSpacing(6)

        self.icon_btn = SvgButton(self, svg_data=square_icon)
        self.label = NotifyLabel(self)
        layout.addWidget(self.icon_btn)
        layout.addWidget(self.label)

        # 待显示内容 (message, icon, duration)，在动画暗下瞬间的 on_show 消费
        self._pending = None

        # 单一成员定时器：新消息覆盖时重置计时，避免 singleShot 堆积
        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self._quit)

    def post_message(self, message: str, icon: str | None, duration: int):
        """登记一条消息并立即切入本页（由模块级 notify() 调用，仅限主线程）"""
        # 取消上一条的自动退出：避免旧定时器在新消息的切换动画期间触发，
        # 直接把尚未显示出来的新消息顶掉
        self._exit_timer.stop()
        self._pending = (message, icon, duration)
        # target_size 必须在 immediate_switch 之前更新：
        # switch_to 在动画启动时读取它来决定容器目标几何
        self.target_size = self._measure(message, icon)
        page_router.immediate_switch(self.page_name)

    def on_show(self):
        """动画透明度暗下瞬间应用待显示内容，并从可见时刻起计自动退出"""
        if self._pending is None:
            return
        message, icon, duration = self._pending
        self._pending = None

        if icon:
            self.icon_btn.set_svg(icon)
            self.icon_btn.show()
        else:
            self.icon_btn.hide()
        self.label.set_text(message)

        if duration > 0:
            self._exit_timer.start(duration)

    def clear_data(self):
        """提前退出（Esc / 被顶出队列）时丢弃未显示内容并停表"""
        self._pending = None
        self._exit_timer.stop()

    def _measure(self, message: str, icon: str | None) -> tuple[int, int]:
        """按消息长度计算 target_size：单行按内容定宽，超宽封顶（不换行，超长部分裁掉）"""
        fm = QFontMetrics(self.label.font())
        assert self.main_layout is not None
        icon_w = (self.icon_btn.width() + self.main_layout.spacing()) if icon else 0
        # 固定开销：容器左右边距 20 + 关闭按钮 36 + 与内容区的间距 6 + 度量余量 12
        chrome = 20 + 36 + 6 + 15

        text_w = fm.horizontalAdvance(message)
        width = max(chrome + icon_w + text_w, self.MIN_WIDTH)
        return (min(width, self.MAX_WIDTH), self.BASE_HEIGHT)

    def _quit(self):
        page_router.exit_self(self.page_name)


def notify(
    message: str,
    icon: str | None = None,
    duration: int = 1500,
    only_when_idle: bool = False,
):
    """全局通知入口，任何模块调用即弹出通知（须在主线程调用）。

    :param message: 消息文本
    :param icon: 消息图标（resources.svgs 中的 SVG 数据），None 不显示图标
    :param duration: 停留毫秒数；<= 0 表示常驻，直到被下一条消息覆盖
    :param only_when_idle: True 时，若当前正显示 home/通知页以外的页面则丢弃
        消息（如剪贴板提醒不打断使用中的页面）；False 时无条件插队提醒
        （如触摸板切换，与旧版行为一致）
    """
    page = page_router.pages.get(NotifyPage.PAGE_NAME)
    if page is None:
        print("[notify] 通知页尚未注册，丢弃消息:", message)
        return
    if only_when_idle:
        current = page_router.page_queue[0] if page_router.page_queue else "home"
        if current not in ("home", NotifyPage.PAGE_NAME):
            return
    page.post_message(message, icon, duration)
