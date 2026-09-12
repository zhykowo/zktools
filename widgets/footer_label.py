# footer_label.py
"""底部状态栏用的灰色小字标签。

qr_code / note / text_recognition 三个页面原本各自写了一份
`_make_footer_label()`，样式完全一样（11px + NEUTRAL_4），这里抽成公共组件。
"""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QWidget

from core.colors import NEUTRAL_4

# 小字字号（像素）
FOOTER_FONT_PIXEL_SIZE = 11


class FooterLabel(QLabel):
    """底部状态栏小字标签：11px 灰色文字，用于状态提示、字数统计等次要信息"""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)

        font = self.font()
        font.setPixelSize(FOOTER_FONT_PIXEL_SIZE)
        self.setFont(font)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, NEUTRAL_4)
        self.setPalette(palette)
