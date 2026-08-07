# colors.py
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette

def get_purest_color(color: QColor) -> QColor:
  """获取输入颜色对应的最纯净版本（最高饱和度 & 明度）"""
  h, s, v, a = color.getHsv()

  if h == -1:
    return QColor(color)

  return QColor.fromHsv(h, s, v, a)

def get_accent_color():
    purest_color = get_purest_color(QApplication.palette().color(QPalette.ColorRole.Accent))
    # purest_color.darker(120)
    return purest_color
