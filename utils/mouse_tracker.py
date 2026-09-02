from PySide6.QtCore import QEvent, QObject


def _safe_print(*args):
    """控制台编码不安全时降级为纯文本，避免 GBK/ASCII 环境下打印崩溃"""
    try:
        print(*args)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("utf-8", "replace").decode("ascii", "replace"))


# 全局鼠标追踪事件过滤器
class MouseHoverEventFilter(QObject):
    """全局鼠标追踪事件过滤器，用于调试追踪当前鼠标下的控件（悬停 / 点击）"""

    def __init__(self, debug_enabled=True):
        super().__init__()
        self.debug_enabled = debug_enabled
        # 用于去重，避免重复打印同一个控件的进入事件
        self.last_hovered_widget = None
        # 过滤掉一些频繁触发但无用的控件（可选）
        # 比如 QWidget, QGraphicsOpacityEffect 等内部控件
        self.ignore_classes = [
            "QGraphicsOpacityEffect",
            "QGraphicsEffectSource",
            "QWidget",
        ]
        # 鼠标按钮 -> 中文名映射（Qt.MouseButton 取值）
        self.button_names = {
            1: "左键",
            2: "右键",
            4: "中键",
        }

    def _widget_info(self, obj):
        """获取控件的 objectName 与类名"""
        obj_name = obj.objectName() or "未命名"
        class_name = obj.metaObject().className()
        return obj_name, class_name

    def _is_ignored(self, class_name):
        return class_name in self.ignore_classes

    def eventFilter(self, obj, event):
        if not self.debug_enabled:
            return False

        if event.type() == QEvent.Type.Enter:
            obj_name, class_name = self._widget_info(obj)
            if self._is_ignored(class_name):
                return False
            # 去重：同一个控件只打印一次进入事件
            if self.last_hovered_widget != obj:
                self.last_hovered_widget = obj
                _safe_print(f"🖱️ 鼠标进入: {obj_name} ({class_name})")

        # 可选：监听离开事件
        elif event.type() == QEvent.Type.Leave:
            obj_name, class_name = self._widget_info(obj)
            # 打印离开事件（如需启用，取消注释即可）
            # print(f"⬅️ 鼠标离开: {obj_name} ({class_name})")

        # 鼠标按下时输出点击的组件
        elif event.type() == QEvent.Type.MouseButtonPress:
            obj_name, class_name = self._widget_info(obj)
            if self._is_ignored(class_name):
                return False
            button = event.button()
            button_name = self.button_names.get(button.value, str(button))
            pos = event.position()
            _safe_print(
                f"🖱️ 鼠标点击: {obj_name} ({class_name}) [按钮: {button_name} @({int(pos.x())},{int(pos.y())})]"
            )

        return False
