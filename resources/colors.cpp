#include "resources/colors.h"

#include <QApplication>
#include <QPalette>

namespace Colors {

QColor defaultAccent() { return QColor(0, 120, 215); }

QColor neutral0() { return QColor(QStringLiteral("#1d1d1f")); }
QColor neutral1() { return QColor(QStringLiteral("#26262b")); }
QColor neutral2() { return QColor(QStringLiteral("#3a3a3d")); }
QColor neutral3() { return QColor(QStringLiteral("#5c5c62")); }
QColor neutral4() { return QColor(QStringLiteral("#8b8b8b")); }
QColor neutral5() { return QColor(QStringLiteral("#CCCCCC")); }
QColor white()    { return QColor(QStringLiteral("#FFFFFF")); }

QColor danger()      { return QColor(QStringLiteral("#E81123")); }
QColor transparent() { return QColor(0, 0, 0, 0); }

QString toQssColor(const QColor& color)
{
    if (color.alpha() < 255)
        return QStringLiteral("rgba(%1, %2, %3, %4)")
            .arg(color.red()).arg(color.green()).arg(color.blue()).arg(color.alpha());
    return color.name();
}

QColor getPurestColor(const QColor& color)
{
    int h, s, v, a;
    color.getHsv(&h, &s, &v, &a);
    if (h == -1)
        return QColor(color);
    return QColor::fromHsv(h, s, int(v * 0.9), a);
}

QColor getAccentColor()
{
    QColor accent = QApplication::palette().color(QPalette::Accent);
    if (!accent.isValid() || accent.value() < 40)
        accent = defaultAccent();
    return getPurestColor(accent);
}

} // namespace Colors
