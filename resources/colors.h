#pragma once

// 统一配色管理：所有界面颜色集中定义，避免散落的魔法色值（对应 resources/colors.py）
// 深色主题灰阶 NEUTRAL_0 ~ NEUTRAL_5 + WHITE；getAccentColor() 读取系统强调色并保底。

#include <QColor>
#include <QString>

namespace Colors {

// 系统未提供有效 Accent 色时的默认强调色（Windows 经典强调蓝 #0078D7）
QColor defaultAccent();

// 中性灰阶（深色主题统一配色）：亮度从暗到亮单调递增
QColor neutral0();          // 最暗：窗口 / 主容器基底背景
QColor neutral1();          // 暗灰：输入框等表面背景
QColor neutral2();          // 中暗灰：按钮背景 / 常态边框
QColor neutral3();          // 中灰：悬停边框 / 外框渐变暗端
QColor neutral4();          // 亮灰：占位文字 / 禁用态 / 虚线 / 渐变亮端
QColor neutral5();          // 浅灰：次级文字
QColor white();             // 纯白：主文字 / 图标

// 功能色
QColor danger();            // 危险 / 关闭按钮 hover
QColor transparent();       // 全透明（palette Base / QSS 通用）

// 把 QColor 转换为 QSS 可用的颜色字符串（保留 alpha）
QString toQssColor(const QColor& color);

// 获取输入颜色对应的最纯净版本（最高饱和度 & 明度）
QColor getPurestColor(const QColor& color);

// 获取系统强调色（无效 / 接近黑色时回退默认配色）
QColor getAccentColor();

} // namespace Colors
