from PySide6.QtCore import QEvent, QObject

# 全局鼠标追踪事件过滤器
class MouseHoverEventFilter(QObject):
    """全局鼠标悬停事件过滤器，用于调试追踪当前鼠标下的控件"""
    
    def __init__(self, debug_enabled=True):
        super().__init__()
        self.debug_enabled = debug_enabled
        # 用于去重，避免重复打印同一个控件的进入事件
        self.last_hovered_widget = None
    
    def eventFilter(self, obj, event):
        if not self.debug_enabled:
            return False
            
        if event.type() == QEvent.Type.Enter:
            # 获取控件信息
            obj_name = obj.objectName() or "未命名"
            class_name = obj.metaObject().className()
            
            # 过滤掉一些频繁触发但无用的控件（可选）
            # 比如 QWidget, QGraphicsOpacityEffect 等内部控件
            ignore_classes = ['QGraphicsOpacityEffect', 'QGraphicsEffectSource', 'QWidget']
            if class_name in ignore_classes:
                return False
            
            # 去重：同一个控件只打印一次进入事件
            if self.last_hovered_widget != obj:
                self.last_hovered_widget = obj
                print(f"🖱️ 鼠标进入: {obj_name} ({class_name})")
                
        # 可选：监听离开事件
        elif event.type() == QEvent.Type.Leave:
            obj_name = obj.objectName() or "未命名"
            class_name = obj.metaObject().className()
            # 打印离开事件（如需启用，取消注释即可）
            # print(f"⬅️ 鼠标离开: {obj_name} ({class_name})")
            
        return False