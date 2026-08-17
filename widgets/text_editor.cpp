#include "widgets/text_editor.h"

#include "resources/colors.h"

#include <QFontMetrics>
#include <QPaintEvent>
#include <QPainter>
#include <QPalette>
#include <QPen>
#include <QRectF>

RoundedTextEdit::RoundedTextEdit(const QString& placeholder, const QColor& bgColor,
                                 int radius, QWidget* parent)
    : QTextEdit(parent)
    , m_placeholder(placeholder)
    , m_radius(radius)
{
    m_bgColor = bgColor.isValid() ? bgColor : Colors::neutral1();
    m_accent = Colors::getPurestColor(Colors::getAccentColor());
    m_idleBorder = Colors::neutral2();
    m_hoverBorder = Colors::neutral3();
    m_placeholderColor = Colors::neutral4();

    // 去掉 QTextEdit 自带 frame / 边框，背景交由 paintEvent 统一绘制
    setFrameShape(QFrame::Shape::NoFrame);
    setAcceptRichText(false);
    setStyleSheet(QStringLiteral("QTextEdit { background: transparent; border: none; }"));

    QPalette palette = this->palette();
    palette.setColor(QPalette::ColorRole::Base, Colors::transparent());
    palette.setColor(QPalette::ColorRole::Text, Colors::white());
    palette.setColor(QPalette::ColorRole::Highlight, m_accent);
    palette.setColor(QPalette::ColorRole::HighlightedText, Colors::white());
    setPalette(palette);

    setViewportMargins(0, 0, 0, 0);
    // 文字内边距：让内容与圆角边缘保持呼吸感
    document()->setDocumentMargin(10);
    // 文本变化时刷新 placeholder 的显示状态
    connect(this, &QTextEdit::textChanged, this, [this]() { viewport()->update(); });
}

void RoundedTextEdit::setPlaceholder(const QString& text)
{
    m_placeholder = text;
    viewport()->update();
}

void RoundedTextEdit::paintEvent(QPaintEvent* event)
{
    QWidget* viewportWidget = viewport();

    // 1. 圆角背景（聚焦时轻微提亮，形成层次）
    {
        QPainter painter(viewportWidget);
        painter.setRenderHint(QPainter::RenderHint::Antialiasing);
        const QRectF rect(viewportWidget->rect());

        const QColor bg = hasFocus() ? m_bgColor.lighter(103) : m_bgColor;
        painter.setPen(Qt::PenStyle::NoPen);
        painter.setBrush(bg);
        painter.drawRoundedRect(rect, m_radius, m_radius);

        // 2. 状态边框：聚焦 -> accent；悬停 -> 亮灰；常态 -> 暗灰
        //    （失焦时保持常态灰色：本组件所在主窗口是 Qt.Tool 置顶悬浮窗，
        //     点暗灰再 darker 会与背景几乎同色，看起来像边框"消失"）
        QColor border;
        double width = 1.0;
        if (hasFocus()) {
            border = m_accent;
            width = 2.0;
        } else if (viewportWidget->underMouse() && window()->isActiveWindow()) {
            border = m_hoverBorder;
            width = 1.0;
        } else {
            border = m_idleBorder;
            width = 1.0;
        }

        // 边框矩形内缩 width/2、圆角半径同步减 width/2，使边框外边缘与背景
        // 圆角同心同半径，粗边框时角部也能平滑贴合
        const double half = width / 2.0;
        const QRectF borderRect = rect.adjusted(half, half, -half, -half);
        const double borderRadius = qMax(double(m_radius) - half, 0.0);
        painter.setPen(QPen(border, width));
        painter.setBrush(Qt::BrushStyle::NoBrush);
        painter.drawRoundedRect(borderRect, borderRadius, borderRadius);
    }

    // 3. 默认绘制：文本 + 光标 + 选区（Base 透明，不会覆盖背景）
    QTextEdit::paintEvent(event);

    // 4. placeholder（文本为空且未聚焦时显示）
    if (!m_placeholder.isEmpty() && toPlainText().isEmpty() && !hasFocus()) {
        QPainter p(viewportWidget);
        p.setRenderHint(QPainter::RenderHint::Antialiasing);
        p.setPen(m_placeholderColor);
        p.setFont(font());

        const double margin = document()->documentMargin();
        const QFontMetrics fm = p.fontMetrics();
        const QString text = fm.elidedText(m_placeholder, Qt::TextElideMode::ElideRight,
                                           int(viewportWidget->width() - 2 * margin));
        p.drawText(viewportWidget->rect().adjusted(int(margin), int(margin),
                                                   -int(margin), -int(margin)),
                   Qt::AlignmentFlag::AlignLeft | Qt::AlignmentFlag::AlignTop,
                   text);
    }
}
