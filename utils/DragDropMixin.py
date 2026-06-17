from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent

class DragDropMixin:
    """
    拖放功能混入类。
    任何继承它的 QWidget 都可以直接获得拖放文件的能力，并能通过重写方法自定义行为。
    """

    def init_drag_drop(self):
        # 开启拖放接受
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        # 同时允许 带有文件链接(Urls) 或 纯文本(Text) 的内容拖入
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.on_drag_enter()  # 触发子类的钩子函数
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.on_drag_leave()      # 触发子类的钩子函数
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self.on_drag_leave()      # 放下文件/文本通常也意味着离开拖拽状态
        
        mime_data = event.mimeData()
        
        # 1. 如果拖入的是文件
        if mime_data.hasUrls():
            urls = mime_data.urls()
            file_paths = [url.toLocalFile() for url in urls]
            self.on_files_dropped(file_paths)  # 触发文件处理钩子
            event.acceptProposedAction()
            
        # 2. 如果拖入的是纯文本
        elif mime_data.hasText():
            text = mime_data.text()
            self.on_text_dropped(text)        # 触发文本处理钩子
            event.acceptProposedAction()

    # --- 以下是留给子类实现具体的“业务逻辑”的钩子函数 ---
    def on_drag_enter(self):
        """当文件拖入时要做什么（子类重写）"""
        pass

    def on_drag_leave(self):
        """当文件离开或放下时要做什么（子类重写）"""
        pass

    def on_files_dropped(self, file_paths: list[str]):
        """当文件真正放下时，如何处理这些路径（子类重写）"""
        pass

    def on_text_dropped(self, text: str):
        """当纯文本真正放下时，如何处理这段文字（子类重写）"""
        pass