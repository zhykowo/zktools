#include "widgets/svg_button.h"

#include "resources/colors.h"

#include <QPaintEvent>
#include <QPainter>
#include <QPointF>
#include <QRectF>
#include <QSvgRenderer>
#include <QtGlobal>

SvgButton::SvgButton(QWidget* parent, int size, int iconSize, const QString& svgData,
                     const QColor& hoverColor, bool enableRotation)
    : HoverWidget(parent, HoverShape::Circle)   // 圆形碰撞区域
    , m_iconSize(iconSize)
    , m_normalColor(Colors::white())
    , m_targetColor(hoverColor.isValid() ? hoverColor : Colors::getAccentColor())
    , m_enableRotation(enableRotation)
{
    setFixedSize(size, size);
    setCursor(Qt::PointingHandCursor);

    m_svgRenderer = new QSvgRenderer(this);
    if (!svgData.isEmpty())
        setSvg(svgData);

    // 动画定义
    m_animation = new QPropertyAnimation(this, QByteArrayLiteral("hoverProgress"), this);
    m_animation->setDuration(250);
    m_animation->setEasingCurve(QEasingCurve::InOutCubic);
    m_animation->setStartValue(0.0);
    m_animation->setEndValue(1.0);
}

void SvgButton::onHoverEnter()
{
    m_animation->setDirection(QPropertyAnimation::Forward);
    if (m_animation->state() == QPropertyAnimation::Stopped)
        m_animation->start();
}

void SvgButton::onHoverLeave()
{
    m_animation->setDirection(QPropertyAnimation::Backward);
    if (m_animation->state() == QPropertyAnimation::Stopped)
        m_animation->start();
}

void SvgButton::setHoverProgress(float value)
{
    m_hoverProgress = value;
    update();
}

void SvgButton::setSvg(const QString& svgData)
{
    if (svgData.endsWith(QLatin1String(".svg")))
        m_svgRenderer->load(svgData);
    else
        m_svgRenderer->load(svgData.toUtf8());
    m_iconCache = {};   // 使光栅化缓存失效，下次绘制时重建
    update();
}

// ---------- 光栅化缓存 ----------

void SvgButton::ensureIconCache()
{
    const double dpr = devicePixelRatioF();
    if (!m_iconCache.isNull() && m_cachedDpr == dpr && m_cachedIconSize == m_iconSize)
        return;

    m_iconCache = {};
    m_tintPixmap = {};
    if (!m_svgRenderer->isValid())
        return;

    const int pixSize = int(m_iconSize * dpr);
    QPixmap icon(pixSize, pixSize);
    icon.setDevicePixelRatio(dpr);
    icon.fill(Qt::transparent);
    QPainter painter(&icon);
    m_svgRenderer->render(&painter, QRectF(0, 0, m_iconSize, m_iconSize));
    painter.end();

    m_iconCache = icon;
    m_cachedDpr = dpr;
    m_cachedIconSize = m_iconSize;
}

QPixmap SvgButton::buildTintedPixmap(float p)
{
    if (m_tintPixmap.isNull() || m_tintPixmap.size() != m_iconCache.size()) {
        m_tintPixmap = QPixmap(m_iconCache.size());
        m_tintPixmap.setDevicePixelRatio(m_iconCache.devicePixelRatio());
    }

    const int r = int(m_normalColor.red()
                      + (m_targetColor.red() - m_normalColor.red()) * p);
    const int g = int(m_normalColor.green()
                      + (m_targetColor.green() - m_normalColor.green()) * p);
    const int b = int(m_normalColor.blue()
                      + (m_targetColor.blue() - m_normalColor.blue()) * p);

    QPixmap& tinted = m_tintPixmap;
    tinted.fill(Qt::transparent);
    QPainter painter(&tinted);
    painter.drawPixmap(0, 0, m_iconCache);
    painter.setCompositionMode(QPainter::CompositionMode_SourceIn);
    painter.fillRect(QRectF(0, 0, m_iconSize, m_iconSize), QColor(r, g, b));
    painter.end();
    return tinted;
}

void SvgButton::paintEvent(QPaintEvent*)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    const float p = m_hoverProgress;

    // 绘制背景
    const int bgAlpha = int(p * 40);
    const QColor bgColor(m_targetColor.red(), m_targetColor.green(), m_targetColor.blue(),
                         bgAlpha);
    painter.setPen(Qt::NoPen);
    painter.setBrush(bgColor);
    painter.drawEllipse(rect());

    if (!m_svgRenderer->isValid())
        return;

    // 惰性构建/重建 SVG 光栅化缓存（仅首次 / iconSize / dpr 变化时执行）
    ensureIconCache();
    if (m_iconCache.isNull())
        return;

    // 每帧仅做一次廉价的位图染色（复用成员 pixmap，无分配、无 SVG 重渲染）
    const QPixmap tinted = buildTintedPixmap(p);

    // 绘制
    painter.save();
    painter.translate(width() / 2.0, height() / 2.0);
    if (m_enableRotation)
        painter.rotate(-p * 90.0);
    painter.drawPixmap(QPointF(-m_iconSize / 2.0, -m_iconSize / 2.0), tinted);
    painter.restore();
}
