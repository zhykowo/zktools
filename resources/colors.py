# colors.py
"""统一配色管理：所有界面颜色集中定义，避免散落的魔法色值。

- 深色主题的全部灰色收敛为一组固定中性灰阶（NEUTRAL_0 ~ NEUTRAL_5 + WHITE），
  各语义颜色统一从这里引用，保证风格统一；
- get_accent_color() 读取系统强调色，并内置保底机制：
  当系统未提供有效 Accent 色时，自动回退到默认配色 DEFAULT_ACCENT。
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette


# ============ 保底默认强调色 ============
# 系统未提供有效 Accent 色时使用的默认强调色（Windows 经典强调蓝 #0078D7）
DEFAULT_ACCENT = QColor(0, 120, 215)
DEFAULT_ACCENT_HEX = "#0078D7"


# ============ 中性灰阶（深色主题统一配色） ============
# 固定灰阶：所有语义颜色统一从这些中性色阶引用，避免散落的灰色值。
# 亮度从暗到亮单调递增，保证 hover 边框 < 占位文字 < 次级文字 的可读性层次。
NEUTRAL_0 = QColor("#1d1d1f")   # 最暗：窗口 / 主容器基底背景
NEUTRAL_1 = QColor("#26262b")   # 暗灰：输入框等表面背景
NEUTRAL_2 = QColor("#3a3a3d")   # 中暗灰：按钮背景 / 常态边框
NEUTRAL_3 = QColor("#5c5c62")   # 中灰：悬停边框 / 外框渐变暗端
NEUTRAL_4 = QColor("#8b8b8b")   # 亮灰：占位文字 / 禁用态 / 虚线 / 渐变亮端
NEUTRAL_5 = QColor("#CCCCCC")   # 浅灰：次级文字
WHITE     = QColor("#FFFFFF")   # 纯白：主文字 / 图标

# ---- 功能色 ----
COLOR_DANGER = QColor("#E81123")        # 危险 / 关闭按钮 hover

# ---- 透明 ----
COLOR_TRANSPARENT = QColor(0, 0, 0, 0)  # 全透明（palette Base / QSS 通用）


def to_qss_color(color: QColor) -> str:
    """把 QColor 转换为 QSS 可用的颜色字符串（保留 alpha）"""
    if color.alpha() < 255:
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
    return color.name()


def get_purest_color(color: QColor) -> QColor:
  """获取输入颜色对应的最纯净版本（最高饱和度 & 明度）"""
  h, s, v, a = color.getHsv()

  if h == -1:
    return QColor(color)

  return QColor.fromHsv(h, s, int(v*0.9), a)


def get_accent_color() -> QColor:
    """获取系统强调色。

    保底机制：当系统未提供有效的 Accent 色（无效色 / 接近黑色）时，
    回退到默认配色 DEFAULT_ACCENT，保证界面风格始终统一。
    """
    try:
        accent = QApplication.palette().color(QPalette.ColorRole.Accent)
    except Exception:
        accent = QColor()

    if not accent.isValid() or accent.value() < 40:
        # 保底：系统未提供有效强调色时使用默认配色
        accent = QColor(DEFAULT_ACCENT)

    return get_purest_color(accent)
