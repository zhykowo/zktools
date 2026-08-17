#include "widgets/hover.h"

#include <QMouseEvent>
#include <QPainterPath>
#include <QRectF>

HoverWidget::HoverWidget(QWidget* parent, HoverShape::Kind shape, double borderRadius)
    : QWidget(parent)
    , m_shape(shape)
    , m_borderRadius(borderRadius)
{
    // 强制开启悬停属性与追踪
    setAttribute(Qt::WA_Hover, true);
    setAttribute(Qt::WA_TranslucentBackground, true);
    setMouseTracking(true);
}

void HoverWidget::setHoverShape(HoverShape::Kind shape, double borderRadius)
{
    m_shape = shape;
    m_borderRadius = borderRadius;
    update();
}

QPainterPath HoverWidget::getCustomPath() const
{
    QPainterPath path;
    path.addRect(rect());
    return path;
}

bool HoverWidget::containsPoint(const QPointF& pos) const
{
    // 根据当前设定的几何形状，精准检测点是否在内部
    const qreal x = pos.x();
    const qreal y = pos.y();
    const int w = width();
    const int h = height();

    switch (m_shape) {
    case HoverShape::Rectangle:
        return rect().contains(x, y);

    case HoverShape::Circle: {
        const qreal cx = w / 2.0, cy = h / 2.0;
        const qreal dx = x - cx, dy = y - cy;
        const qreal radius = qMin(w, h) / 2.0;
        return (dx * dx + dy * dy) <= (radius * radius);
    }

    case HoverShape::RoundedRect: {
        QPainterPath path;
        path.addRoundedRect(QRectF(rect()), m_borderRadius, m_borderRadius);
        return path.contains(pos);
    }

    case HoverShape::Custom:
        return getCustomPath().contains(pos);
    }
    return false;
}

bool HoverWidget::event(QEvent* event)
{
    if (event->type() == QEvent::HoverMove || event->type() == QEvent::MouseMove) {
        QPointF pos;
        if (event->type() == QEvent::HoverMove)
            pos = static_cast<QHoverEvent*>(event)->position();
        else
            pos = static_cast<QMouseEvent*>(event)->position();
        updateHoverState(containsPoint(pos));

    } else if (event->type() == QEvent::HoverLeave || event->type() == QEvent::Leave) {
        updateHoverState(false);
    }

    return QWidget::event(event);
}

void HoverWidget::updateHoverState(bool isHovered)
{
    if (m_isHovered == isHovered)
        return;

    m_isHovered = isHovered;
    if (isHovered) {
        onHoverEnter();
        emit hoverEntered();
    } else {
        onHoverLeave();
        emit hoverLeft();
    }
}

void HoverWidget::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton) {
        if (containsPoint(event->position()))
            m_isPressed = true;
    }
    QWidget::mousePressEvent(event);
}

void HoverWidget::mouseReleaseEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton && m_isPressed) {
        m_isPressed = false;
        if (containsPoint(event->position()))
            emit clicked(false);
    }
    QWidget::mouseReleaseEvent(event);
}
