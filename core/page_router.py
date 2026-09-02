"""页面路由（单例）：信号入口 + 全局状态 + 切换调度，三合一。

合并自原 core/page_controller.py（page_signals 信号）、core/page_state.py
（page_state 状态）与 core/page_router.py（page_router 调度）三个模块，
子模块只需从一处导入：

    from core.page_router import page_router

    page_router.immediate_switch("setting")            # 发切换请求
    page_router.exit_self("short_text")                # 精确退出指定页
    page_router.gentle_switch("translator")            # 温和排队切换

    if page_router.page_queue and page_router.page_queue[0] == "setting":  # 读当前页（队首）
        ...
    page_router.page_queue.append("translator")        # 直接操作队列
"""

from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class SwitchMode(Enum):
    GENTLE = auto()  # 温和切换：加入队列排队
    IMMEDIATE = auto()  # 立即切换：插队并强制中断当前页面
    EXIT_SELF = auto()  # 退出自己：当前页面结束，释放并展示队列下一页


class PageRouter(QObject):
    """页面路由单例（见文件底部 page_router 实例）。

    一个对象同时承担三种职责：
    - 信号入口：gentle_switch / immediate_switch / exit_self 发出切换请求；
    - 全局状态：pages / page_queue 供任意子模块读写；
    - 调度逻辑：dispatch / next_page 消费请求并驱动页面渲染。

    约定：page_queue 的队首（page_queue[0]）即当前正在显示的页面，
    不再单独维护 current_page_name；队列正常至少保留 "home"（清空后自动补回）。
    """

    page_action = Signal(object, str)  # 传递 切换模式 和 目标页面标识

    def __init__(self):
        super().__init__()

        # 全局状态
        self.pages = {}  # 页面注册池 { "page_name": widget_instance }
        self.page_queue = []  # 页面队列 [page_name, ...]，队首即当前显示页；至少保留 "home"

        # 协作对象（主窗口通过 bind() 注入，避免反向依赖窗口实例）
        self.window_manager = None  # core.window_manager.WindowManager
        self.animation_manager = None  # core.page_animation.PageAnimationManager

        # 单例导入即接管全局路由请求，无需手动连接
        self.page_action.connect(self.dispatch)

    def bind(self, window_manager=None, animation_manager=None):
        """主窗口在初始化完成后注入 UI 协作对象。"""
        if window_manager is not None:
            self.window_manager = window_manager
        if animation_manager is not None:
            self.animation_manager = animation_manager
            # 透明度完全暗下（页面切换完成）的瞬间才触发目标页 on_show
            self.animation_manager.page_switched.connect(self._on_page_switched)
        return self

    def register_virtual(self, page):
        """注册无界面模块（pages.notify_page.VirtualPage 实例，"假页面"）。

        只进入页面池供模块中心枚举卡片，不加入堆叠窗口；
        dispatch 会拒绝把虚拟页面作为切换目标。
        """
        self.pages[page.PAGE_NAME] = page
        page.page_name = page.PAGE_NAME
        return page

    def _on_page_switched(self, page_name: str):
        """动画透明度暗下、页面索引切换完成时，调用目标页的 on_show"""
        page = self.pages.get(page_name)
        if page is not None:
            page.on_show()

    # ---------- 信号入口 ----------
    def gentle_switch(self, page_name: str):
        """温和切换：仅加入队列"""
        self.page_action.emit(SwitchMode.GENTLE, page_name)

    def immediate_switch(self, page_name: str):
        """立即切换：立刻中断并显示目标页"""
        self.page_action.emit(SwitchMode.IMMEDIATE, page_name)

    def exit_self(self, page_name: str = ""):
        """退出指定页面：通知调度器调度下一页

        - 带 page_name：精确退出该页面（若它是当前页则调度下一页，
          若它在队列中则直接移除），避免退错正在显示的页面。
        - 不带参数：保持旧语义，退出当前正在显示的页面。
        """
        self.page_action.emit(SwitchMode.EXIT_SELF, page_name)

    # ---------- 调度逻辑 ----------
    def dispatch(self, mode: SwitchMode, page_name: str):
        """核心路由控制阀：按模式调度页面。"""
        if self.window_manager is None or self.animation_manager is None:
            print(
                "[page_router] 尚未 bind 窗口管理器/动画管理器，忽略路由请求:",
                mode,
                page_name,
            )
            return

        # 温和/立即切换的目标必须是可显示的实体页面：
        # 未注册或虚拟页面（无界面模块）直接忽略，避免无界面对象进入队列/动画
        if mode != SwitchMode.EXIT_SELF:
            page = self.pages.get(page_name)
            if page is None or getattr(page, "virtual", False):
                print("[page_router] 忽略对不可显示页面的切换请求:", page_name)
                return

        self.window_manager.queue_state = True
        self.window_manager.animate(True)

        if mode == SwitchMode.GENTLE:
            # 1. 温和切换：仅塞入队列（已在队列中则跳过，保证队列有界、不重复排队）
            was_idle = not self.page_queue  # 无当前页（仅异常兜底，正常至少含 "home"）
            if page_name not in self.page_queue:
                self.page_queue.append(page_name)
            # 若当前页为 home（处于空闲）则直接触发下一页
            if was_idle or self.page_queue[0] == "home":
                self.next_page()

        elif mode == SwitchMode.IMMEDIATE:
            # 2. 立即切换：插队逻辑
            if not self.page_queue or self.page_queue[0] != page_name:
                # 目标页成为新的当前页（队首）；原当前页留在队列中等待其退出后无缝恢复。
                # 去重：若目标页已在队列中排队，先移除旧位置，避免高频触发下队列无限增长。
                if page_name in self.page_queue:
                    self.page_queue.remove(page_name)
                self.page_queue.insert(0, page_name)

            # on_show 由动画透明度暗下瞬间的 page_switched 信号触发
            self.animation_manager.switch_to(self.pages[page_name], page_name)

        elif mode == SwitchMode.EXIT_SELF:
            # 精确退出：page_name 指定要退出的页面，而不是盲目退当前页
            if page_name:
                if self.page_queue and self.page_queue[0] == page_name:
                    # 目标页面正在显示（队首）：清数据并调度下一页
                    current_page = self.pages.get(page_name)
                    if current_page and hasattr(current_page, "clear_data"):
                        current_page.clear_data()
                    self.next_page()
                elif page_name in self.page_queue:
                    # 目标页面被插队顶到队列中：直接从队列移除，无需切换
                    self.page_queue.remove(page_name)
                # 否则：目标页面既不在当前也不在队列，什么都不做

    def next_page(self):
        """队首即当前页：弹出旧当前页，新队首成为当前页并渲染；队列清空则回到 home"""
        if self.page_queue:
            # 弹出旧当前页（队首），新队首自动成为当前页
            self.page_queue.pop(0)
        if not self.page_queue:
            # 队列清空（退出最后一页/异常兜底）：补回 home，保持"队首即当前页"且队列至少含 home
            self.page_queue.append("home")
        next_name = self.page_queue[0]
        if self.animation_manager is None:
            return
        # on_show 由动画透明度暗下瞬间的 page_switched 信号触发
        self.animation_manager.switch_to(self.pages[next_name], next_name)
        if next_name == "home" and self.window_manager is not None:
            # 显示/回到 home：归位居中显示
            self.window_manager.queue_state = False
            self.window_manager.animate(
                show=self.window_manager.on_focus, recenter=True
            )


page_router = PageRouter()
