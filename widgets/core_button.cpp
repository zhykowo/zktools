#include "widgets/core_button.h"

#include "resources/colors.h"

#include <QBrush>
#include <QPaintEvent>
#include <QPainter>
#include <QPen>
#include <QRectF>

CoreButton::CoreButton(const QString& text, const QColor& bgColor, const QColor& textColor,
                       int radius, QWidget* parent)
    : QPushButton(text, parent)
    , m_radius(radius)
{
    m_accentQColor = Colors::getPurestColor(Colors::getAccentColor());
    m_bgColor = bgColor.isValid() ? bgColor : m_accentQColor;
    m_textColor = textColor.isValid() ? textColor : Colors::white();
}

void CoreButton::paintEvent(QPaintEvent*)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::RenderHint::Antialiasing);

    // 1. 状态判断 (Disabled -> Pressed -> Hover -> Normal)
    QColor bgColor;
    if (!isEnabled()) {
        bgColor = Colors::neutral4();
    } else if (isDown()) {          // 点击按下状态
        bgColor = m_bgColor.darker(120);
    } else if (underMouse()) {      // 悬停 Hover 状态
        bgColor = m_bgColor.lighter(110);
    } else {                        // 正常状态
        bgColor = m_bgColor;
    }

    // 2. 绘制背景（固定圆角，参考 text_editor 的圆角风格）
    painter.setPen(Qt::PenStyle::NoPen);
    painter.setBrush(QBrush(bgColor));
    painter.drawRoundedRect(rect(), m_radius, m_radius);

    // 3. 圆角边框：颜色取决于当前背景色，圆角采用同心内缩画法，粗角处也能平滑贴合
    const QColor borderColor = bgColor.lighter(120);
    constexpr double half = 1.0;
    const QRectF borderRect = QRectF(rect()).adjusted(half, half, -half, -half);
    const double borderRadius = qMax(double(m_radius) - half, 0.0);
    painter.setPen(QPen(borderColor, 1.0));
    painter.setBrush(Qt::BrushStyle::NoBrush);
    painter.drawRoundedRect(borderRect, borderRadius, borderRadius);

    // 4. 绘制文字
    painter.setPen(m_textColor);
    painter.setFont(font());
    painter.drawText(rect(), Qt::AlignmentFlag::AlignCenter, text());
}

void CoreButton::setBgColor(const QColor& bgColor)
{
    m_bgColor = bgColor;
    update();
}

void CoreButton::resetBgColor()
{
    m_bgColor = m_accentQColor;
    update();
}
