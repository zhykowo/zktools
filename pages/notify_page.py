"""全局通知页：所有瞬时消息提醒的统一出口，由 main.py 注册一次（全局单例）。

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
  都重新读取 target_size，允许频繁修改）；过长消息自动封顶宽度并按
  换行行数增高；
- duration <= 0 表示常驻，直到被下一条消息覆盖（触摸板"切换中"状态用）。
"""
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel

from core.page_router import page_router

from pages.base_page import BasePage
from widgets.svg_button import SvgButton

from resources.svgs import square_icon


class NotifyPage(BasePage):
    """通知页（瞬时消息页）：仅经 notify() 驱动显示，不出现在模块中心"""

    PAGE_NAME = "notify"
    TITLE = "Notify"

    MAX_WIDTH = 430    # 主窗口 450 - 容器左右边距 10 * 2
    MIN_WIDTH = 160
    BASE_HEIGHT = 50   # 单行消息高度，与旧 clipboard/touchpad 通知尺寸一致
    MAX_HEIGHT = 360   # 容器顶边固定 y=40，封顶以保证不超出 400 高的窗口

    def __init__(self, parent=None):
        super().__init__(parent)

        self.target_size = (self.MIN_WIDTH, self.BASE_HEIGHT)

        layout = self.set_main_layout('h')
        self.main_layout.setSpacing(6)
        layout.setSpacing(6)

        self.icon_btn = SvgButton(self, size=20, icon_size=16, svg_data=square_icon)
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(True)
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
        self.label.setText(message)

        if duration > 0:
            self._exit_timer.start(duration)

    def clear_data(self):
        """提前退出（Esc / 被顶出队列）时丢弃未显示内容并停表"""
        self._pending = None
        self._exit_timer.stop()

    def _measure(self, message: str, icon: str | None) -> tuple[int, int]:
        """按消息长度计算 target_size：单行按内容定宽，超宽封顶换行、按行数增高"""
        fm = QFontMetrics(self.label.font())
        icon_w = (self.icon_btn.width() + self.main_layout.spacing()) if icon else 0
        # 固定开销：容器左右边距 20 + 关闭按钮 36 + 与内容区的间距 6 + 度量余量 12
        chrome = 20 + 36 + 6 + 12

        text_w = fm.horizontalAdvance(message)
        width = max(chrome + icon_w + text_w, self.MIN_WIDTH)
        if width <= self.MAX_WIDTH:
            return (width, self.BASE_HEIGHT)

        # 过长消息：封顶宽度，按可用文本宽度换行计算高度
        text_avail = self.MAX_WIDTH - chrome - icon_w
        rect = fm.boundingRect(
            QRect(0, 0, text_avail, self.MAX_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            message,
        )
        height = max(self.BASE_HEIGHT, rect.height() + 24)
        return (self.MAX_WIDTH, min(height, self.MAX_HEIGHT))

    def _quit(self):
        page_router.exit_self(self.page_name)


def notify(message: str, icon: str | None = None, duration: int = 1500,
           only_when_idle: bool = False):
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
