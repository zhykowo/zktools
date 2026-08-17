#include "widgets/main_container.h"

#include "resources/colors.h"

#include <QLinearGradient>
#include <QPaintEvent>
#include <QPainter>
#include <QPen>
#include <QRectF>

MainContainerWidget::MainContainerWidget(QWidget* parent)
    : QWidget(parent)
{
    m_defaultBackgroundColor = Colors::neutral0();
    m_backgroundColor = m_defaultBackgroundColor;
    // 外边框使用渐变描边：左上亮（白）→ 右下暗（灰），比单色更有层次
    m_borderColorStart = Colors::neutral4();
    m_borderColorEnd = Colors::neutral3();
}

void MainContainerWidget::setBackgroundColor(const QColor& color)
{
    m_backgroundColor = color;
    update();
}

void MainContainerWidget::setRadius(int radius)
{
    m_currentRadius = radius;
    update();
}

void MainContainerWidget::paintEvent(QPaintEvent*)
{
    // 使用 QPainter 纯原生高效绘制圆角矩形 + 细边框
    QPainter painter(this);
    painter.setRenderHint(QPainter::RenderHint::Antialiasing);

    // 绘制抗锯齿圆角背景（用完整矩形，保证填充不留毛边）
    painter.setPen(Qt::PenStyle::NoPen);
    painter.setBrush(m_backgroundColor);
    painter.drawRoundedRect(rect(), m_currentRadius, m_currentRadius);

    // 绘制外圈渐变边框。中心线矩形内缩 w/2、圆角半径取 R - w/2，
    // 使边框外边缘与背景圆角同心同半径，粗边框时角部也能平滑贴合
    const double half = m_borderWidth / 2.0;
    const QRectF borderRect = QRectF(rect()).adjusted(half, half, -half, -half);
    const double borderRadius = m_currentRadius - half;
    QLinearGradient gradient(borderRect.topLeft(), borderRect.bottomRight());
    gradient.setColorAt(0.0, m_borderColorStart);   // 左上：白
    gradient.setColorAt(1.0, m_borderColorEnd);     // 右下：灰
    painter.setPen(QPen(QBrush(gradient), m_borderWidth));
    painter.setBrush(Qt::BrushStyle::NoBrush);
    painter.drawRoundedRect(borderRect, borderRadius, borderRadius);
}
