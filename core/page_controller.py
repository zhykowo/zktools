from enum import Enum, auto
from PySide6.QtCore import QObject, Signal

class SwitchMode(Enum):
    GENTLE = auto()      # 温和切换：加入队列排队
    IMMEDIATE = auto()   # 立即切换：插队并强制中断当前页面
    EXIT_SELF = auto()   # 退出自己：当前页面结束，释放并展示队列下一页

class PageController(QObject):
    """页面路由控制器"""
    page_action = Signal(object, str)  # 传递 切换模式 和 目标页面标识
    
    def __init__(self):
        super().__init__()
    
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

page_signals = PageController()
