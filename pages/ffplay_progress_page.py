"""ffplay 播放进度页：监听 \\\\.\\pipe\\ffplay_progress 管道的实时进度展示。

- 纯文字（QLabel）单行显示，两个标签拼接：
  - 名称标签：弹性宽度，超长按可用宽度省略（…），保证不挤占进度区；
  - 进度标签：按当前实际文本动态测宽，时间/百分比永远完整显示；
- h 布局（同通知页的紧凑样式：无标题栏，内容区 + 全局关闭按钮）；
- 只显示**最新更新**的那个视频：收到不同 video_path 的进度直接整体替换；
- 收到任何进度更新时，若当前显示的不是本页则立即切换（immediate_switch）；
- 用户可主动"收起"本页（点击图标 / Esc）：收起后退出本页且**不再自动展开**，
  后台仍持续接收并静默更新内容，直到本轮播放结束（_sweep_stale 判定停播）才解除限制；
- 长期没有更新（超过 STALE_SECONDS）自动清空并退回上一页；
- MODULE_NAME 为空：不出现在模块中心；
- target_size 按内容动态计算（PageAnimationManager 每次切换都重新读取）。

数据源见 utils/ffplay_progress_monitor.py（管道协议与 test.py 一致）。
"""

import logging
import os
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics, QPalette
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.colors import WHITE
from core.page_router import page_router
from pages.base_page import BasePage
from resources.svgs import video_icon
from utils import ffplay_progress_monitor
from widgets.svg_button import SvgButton

logger = logging.getLogger(__name__)

STALE_SECONDS = 1.0  # 超过该时长没有更新视为停止播放，自动清空退页
BASE_HEIGHT = 50  # 单行高度（同通知页）
MIN_WIDTH = 160
MAX_WIDTH = 430  # 主窗口 450 - 容器左右边距 10 * 2

# 进度标签的最小宽度度量模板：保证即使进度文本很短，也不会窄到抖动。
# 注意：这里不再用最长模板锁死宽度，真正宽度按当前文本动态计算。
PROGRESS_MIN_TEMPLATE = "0:00 / 0:00  (0%)"


def _fmt_sec(sec: float) -> str:
    """秒数格式化为 m:ss / h:mm:ss"""
    sec = max(int(sec), 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class FfplayProgressPage(BasePage):
    """播放进度页：单视频显示（永远跟随最新更新的那个），不进模块中心"""

    PAGE_NAME = "ffplay_progress"
    TITLE = "Ffplay Progress"
    MODULE_NAME = None  # 空值：模块中心不显示本页卡片
    MODULE_ICON = video_icon

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (MIN_WIDTH, BASE_HEIGHT)

        # h 布局：名称 + 进度 + 右侧全局关闭按钮（set_main_layout 自带）
        content = self.set_main_layout("h")
        assert content is not None
        content.setSpacing(0)

        # ICON
        self.icon_button = SvgButton(parent=self, icon_size=20, svg_data=video_icon)
        self.icon_button.clicked.connect(self._temporarily_close)
        content.addWidget(self.icon_button)

        # 名称标签：弹性宽度，文本由本页按可用宽度预先省略
        self.name_label = QLabel("", self)
        font = self.name_label.font()
        font.setPixelSize(13)
        self.name_label.setFont(font)
        palette = self.name_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, WHITE)
        self.name_label.setPalette(palette)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content.addWidget(self.name_label)

        # 进度标签：宽度按当前实际文本动态设置，保证完整显示且不浪费空间
        self.progress_label = QLabel("", self)
        self.progress_label.setFont(font)
        self.progress_label.setPalette(palette)

        fm = QFontMetrics(font)
        self._progress_min_w = fm.horizontalAdvance(PROGRESS_MIN_TEMPLATE) + 4
        self._progress_w = self._progress_min_w
        self.progress_label.setFixedWidth(self._progress_w)
        content.addWidget(self.progress_label)

        # 当前显示的视频路径 + 最近一次更新的单调时钟
        self._video_path = ""
        self._last_seen = 0.0

        # 用户主动收起标记：True 时后台继续接收进度但不再自动展开本页，
        # 直到本轮播放结束（_sweep_stale 判定停播）自动解除
        self._suppressed = False

        # 定期检查是否停止更新（暂停超过 STALE_SECONDS 视为停播）
        self._stale_timer = QTimer(self)
        self._stale_timer.setInterval(1000)
        self._stale_timer.timeout.connect(self._sweep_stale)
        self._stale_timer.start()

        # 连接全局进度信号（监听器未启动时会自动启动）
        ffplay_progress_monitor.connect_progress(self._on_progress)

    # ---------- 信号处理 ----------
    def _on_progress(self, video_path: str, current: float, duration: float):
        """收到一条进度更新：更新显示（不同视频直接整体替换），必要时切页"""
        self._video_path = video_path
        self._last_seen = time.monotonic()

        pct = (current / duration * 100) if duration > 0 else 0.0
        progress_text = f"{_fmt_sec(current)} / {_fmt_sec(duration)}  ({pct:.0f}%)"
        self.progress_label.setText(progress_text)

        # 按当前实际进度文本动态测宽，避免用最长模板导致进度区右侧大片空白
        fm = QFontMetrics(self.progress_label.font())
        progress_w = max(fm.horizontalAdvance(progress_text) + 4, self._progress_min_w)
        if progress_w != self._progress_w:
            self._progress_w = progress_w
            self.progress_label.setFixedWidth(self._progress_w)

        # target_size 必须在 immediate_switch 之前更新：
        # switch_to 在动画启动时读取它来决定容器目标几何
        self.target_size = self._apply_name(os.path.basename(video_path) or video_path)

        # 用户已主动收起：只静默刷新内容（target_size 已同步），不再把本页拉回队首。
        # 限制在新视频开始时由 _sweep_stale 解除，此处无需额外判断。
        if self._suppressed:
            return

        # 有更新且当前显示的不是本页：立即跳转过来（本页已是当前页时不重复切换，
        # 避免每条进度都重放一遍切换动画）
        if page_router.page_queue and page_router.page_queue[0] != self.page_name:
            page_router.immediate_switch(self.page_name)

    def _sweep_stale(self):
        """超时未更新：清空并退回上一页；本轮播放结束同时解除收起限制"""
        # 判停只看"最近一次更新"的时间戳：收起时 clear_data 会清空 _video_path，
        # 若以 _video_path 为判停前提，收起期间恰好播完就再也解不开限制
        if self._last_seen <= 0.0 or time.monotonic() - self._last_seen <= STALE_SECONDS:
            return
        if self._video_path:
            logger.info("[ffplay_progress] 视频停止更新，退页: %s", self._video_path)
            self._clear()
            # 仅当本页仍在显示时才需要退页（收起状态下早已退出队列）
            if page_router.page_queue and page_router.page_queue[0] == self.page_name:
                page_router.exit_self(self.page_name)
        # 本轮播放已结束：解除收起限制，下个视频开始播放时重新自动展开
        self._suppressed = False

    def _temporarily_close(self, _checked: bool = False):
        """暂时收起页面：退出本页并暂停"自动展开"，后台仍持续接收进度。

        - 收起后 _on_progress 只静默更新标签，不再把本页拉回队首；
        - 限制只持续到本轮播放结束（_sweep_stale 判定停播时解除），
          因此下一个视频开始播放时会重新自动展开；
        - 不做退订：管道监听与信号连接保持不变，收起期间不丢任何进度包。
        """
        if self._suppressed:
            return  # 已收起（理论上按钮不可见，这里保证幂等）
        self._suppressed = True
        logger.info("[ffplay_progress] 用户收起进度页，本轮播放不再自动展开: %s", self._video_path)
        # 精确退出本页：队首时调度下一页，仅排队时直接出队，均不影响后台监听
        page_router.exit_self(self.page_name)

    def on_back_clicked(self):
        """Esc / 返回：与图标按钮一致视为"收起"。

        否则普通退出后下一条进度更新（通常几十毫秒内）会立刻把本页切回来，
        页面表现为关不掉；统一走收起逻辑，自然受同一套解除限制约束。
        """
        self._temporarily_close()

    # ---------- 内部辅助 ----------
    def _apply_name(self, name: str) -> tuple[int, int]:
        """把视频名按剩余可用宽度省略后写入名称标签，返回本次 target_size。

        宽度分配：进度区按当前实际文本动态宽度，名称区 = min(全名宽度, 剩余空间)，
        超出部分以 … 截断——保证进度时间永远完整显示，同时名称不会过早截断。
        """
        fm = QFontMetrics(self.name_label.font())
        assert self.main_layout is not None

        # 固定开销：容器左右边距 20 + 关闭按钮 0 + 与内容区的间距 6
        # + 行文本左边距 10 + 度量余量 8
        chrome = 20 + 0 + 6 + 10 + 8

        # 名称与进度标签之间的布局间距 6
        avail_name = max(MAX_WIDTH - chrome - 6 - self._progress_w, 30)
        name_w = min(fm.horizontalAdvance(name), avail_name)
        self.name_label.setText(fm.elidedText(name, Qt.TextElideMode.ElideRight, name_w))

        width = max(chrome + name_w + 6 + self._progress_w, MIN_WIDTH)
        return (min(width, MAX_WIDTH), BASE_HEIGHT)

    def _clear(self):
        self._video_path = ""
        self.name_label.setText("")
        self.progress_label.setText("")
        self._progress_w = self._progress_min_w
        self.progress_label.setFixedWidth(self._progress_w)
        self.target_size = (MIN_WIDTH, BASE_HEIGHT)

    # ---------- 页面生命周期 ----------
    def clear_data(self):
        """退出页面时清空内容（监听仍在运行，有新进度会再次进入本页）"""
        self._clear()
