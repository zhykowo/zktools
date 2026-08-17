#pragma once

// SVG 图标数据（对应 resources/svgs.py）：统一以 QString 形式内嵌，
// 供 SvgButton::setSvg 直接加载（或以 .svg 路径加载）。

#include <QString>

namespace Svgs {

const QString& closeIcon();
const QString& settingsIcon();
const QString& arrowRightIcon();
const QString& arrowLeftIcon();
const QString& appCenterIcon();
const QString& squareIcon();
const QString& dragIcon();
const QString& translateIcon();
const QString& touchpadIcon();
const QString& clipboardIcon();
const QString& noteIcon();

} // namespace Svgs
