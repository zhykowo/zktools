#include "pages/notify_page.h"

#include "core/page_router.h"
#include "resources/colors.h"
#include "resources/svgs.h"
#include "widgets/svg_button.h"

#include <QBrush>
#include <QBoxLayout>
#include <QFont>
#include <QFontMetrics>
#include <QHideEvent>
#include <QPaintEvent>
#include <QPainter>
#include <QPen>
#include <QPointF>
#include <QRectF>
#include <QShowEvent>
#include <QSizePolicy>
#include <QTextOption>
#include <QVBoxLayout>
#include <QtGlobal>
#include <QtMath>

#include <cmath>

// ==================== VirtualPage ====================

VirtualPage::VirtualPage(QObject* parent)
    : QObject(parent)
{
}

QString VirtualPage::moduleIcon() const
{
    return Svgs::squareIcon();
}

void VirtualPage::addModuleNameChangedCallback(std::function<void()> callback)
{
    m_moduleNameCallbacks.push_back(std::move(callback));
}

void VirtualPage::notifyModuleNameChanged()
{
    for (const auto& cb : m_moduleNameCallbacks)
        cb();
}

// ==================== NotifyLabel ====================

NotifyLabel::NotifyLabel(QWidget* parent)
    : QWidget(parent)
{
    setSizePolicy(QSizePolicy::Policy::Expanding, QSizePolicy::Policy::Preferred);

    m_timer.setInterval(16);
    connect(&m_timer, &QTimer::timeout, this, [this]() { update(); });
    m_waveColor = Colors::getAccentColor();
}

void NotifyLabel::setTextAnimated(const QString& text)
{
    // 设置文本并重置逐字动画时钟（同文本重复设置也会重播动画）
    m_text = text;
    m_text.replace(QLatin1Char('\n'), QLatin1Char(' '));
    m_chars = splitChars(m_text);
    m_lines.clear();       // 布局缓存失效，paint 时按当前宽度重建
    m_clock.restart();
    m_timer.start();       // 控件隐藏期间 update() 为空操作，hideEvent 会停表
    update();
}

void NotifyLabel::showEvent(QShowEvent* event)
{
    if (!m_text.isEmpty())
        m_timer.start();
    QWidget::showEvent(event);
}

void NotifyLabel::hideEvent(QHideEvent* event)
{
    m_timer.stop();
    QWidget::hideEvent(event);
}

QVector<NotifyLabel::CharInfo> NotifyLabel::splitChars(const QString& text)
{
    // 逐码点拆分文本：(UTF-16 码元起始位置, 码点)
    QVector<CharInfo> chars;
    const int n = text.size();
    int unit = 0;
    int i = 0;
    while (i < n) {
        const QChar c = text.at(i);
        if (c.isHighSurrogate() && i + 1 < n && text.at(i + 1).isLowSurrogate()) {
            chars.append({unit, text.mid(i, 2)});   // 增补平面字符占两个码元
            unit += 2;
            i += 2;
        } else {
            chars.append({unit, text.mid(i, 1)});
            unit += 1;
            i += 1;
        }
    }
    return chars;
}

void NotifyLabel::ensureLayout()
{
    // 按控件当前宽度（重新）布局文本；文本或宽度变化时重建缓存
    const int width = qMax(this->width(), 1);
    if (!m_lines.isEmpty() && m_layoutWidth == width)
        return;

    m_layout.setText(m_text);
    m_layout.setFont(font());
    QTextOption option;
    option.setWrapMode(QTextOption::WrapMode::NoWrap);
    m_layout.setTextOption(option);

    m_layout.beginLayout();
    m_lines.clear();
    while (true) {
        QTextLine line = m_layout.createLine();
        if (!line.isValid())
            break;
        line.setLineWidth(qMax(double(width), 1.0));
        m_lines.append(line);
    }
    m_layout.endLayout();

    m_layoutWidth = width;
    double y = 0.0;
    for (QTextLine& line : m_lines) {
        line.setPosition(QPointF(0.0, y));
        y += line.height() + LINE_SPACING;
    }
}

void NotifyLabel::paintEvent(QPaintEvent*)
{
    if (m_text.isEmpty())
        return;
    ensureLayout();
    if (m_lines.isEmpty())
        return;

    QPainter painter(this);
    painter.setRenderHint(QPainter::RenderHint::Antialiasing);
    painter.setRenderHint(QPainter::RenderHint::TextAntialiasing);
    painter.setFont(font());

    const qint64 t = m_clock.elapsed();
    const double phase = double(t % WAVE_PERIOD) / double(WAVE_PERIOD);

    // 文本块整体垂直居中
    double totalH = 0.0;
    for (const QTextLine& l : m_lines)
        totalH += l.height();
    totalH += LINE_SPACING * (m_lines.size() - 1);
    const double y0 = qMax((height() - totalH) / 2.0, 0.0);

    const int n = qMax(m_chars.size(), 1);
    const double span = qBound(double(SPAN_MIN),
                               double(SPAN_BASE + SPAN_PER_CHAR * n),
                               double(SPAN_MAX));

    int charPtr = 0;
    QPen pen;
    for (const QTextLine& line : m_lines) {
        const int lineBegin = line.textStart();
        const int lineEnd = lineBegin + line.textLength();
        pen.setBrush(QBrush(lineGradient(line.naturalTextWidth(), phase)));
        painter.setPen(pen);
        const double baseline = y0 + line.position().y() + line.ascent();
        // 单次顺序扫描：全部字符按文本顺序落入各自行内
        while (charPtr < m_chars.size() && m_chars[charPtr].utf16Start < lineEnd) {
            const CharInfo& info = m_chars[charPtr];
            if (info.utf16Start >= lineBegin) {
                const double p = charProgress(charPtr, n, span, double(t));
                if (p > 0.0) {
                    // 位移带回弹地向上冒出，透明度独立淡入
                    const double yOff = DROP_PX * (1.0 - outBack(p));
                    painter.setOpacity(outCubic(p));
                    const qreal x = line.cursorToX(info.utf16Start);
                    painter.drawText(QPointF(x, baseline + yOff), info.ch);
                }
            }
            ++charPtr;
        }
    }
    painter.setOpacity(1.0);
}

double NotifyLabel::charProgress(int k, int n, double span, double t) const
{
    // 启动时刻 start = span * (1 - (1 - k/n)^P)：P > 1 时相邻间隔递减、
    // 浮现节奏逐渐加快；单字动画时长恒定为 CHAR_DURATION。
    const double start = span * (1.0 - std::pow(1.0 - double(k) / double(n), ACCEL_P));
    return qBound(0.0, (t - start) / double(CHAR_DURATION), 1.0);
}

double NotifyLabel::outCubic(double p)
{
    return 1.0 - std::pow(1.0 - p, 3.0);
}

double NotifyLabel::outBack(double p) const
{
    // 带回弹的缓出：字符略微冒过头再落回最终位置
    const double c1 = 1.70158 * BACK_OVERSHOOT;
    const double c3 = c1 + 1.0;
    const double q = p - 1.0;
    return 1.0 + c3 * std::pow(q, 3.0) + c1 * std::pow(q, 2.0);
}

QLinearGradient NotifyLabel::lineGradient(double lineWidth, double phase) const
{
    // 横跨一行宽度的动态渐变：白 ↔ 强调色行波，相位随时间自左向右扫过
    QLinearGradient grad(0.0, 0.0, qMax(lineWidth, 1.0), 0.0);
    const QColor& accent = m_waveColor;
    const QColor white = Colors::white();
    for (int s = 0; s <= WAVE_STOPS; ++s) {
        const double u = double(s) / double(WAVE_STOPS);
        const double wave = (0.5 - 0.5 * std::cos(2.0 * M_PI * (u - phase))) * WAVE_STRENGTH;
        grad.setColorAt(u, QColor(
            qRound(white.red() + (accent.red() - white.red()) * wave),
            qRound(white.green() + (accent.green() - white.green()) * wave),
            qRound(white.blue() + (accent.blue() - white.blue()) * wave)));
    }
    return grad;
}

// ==================== NotifyPage ====================

NotifyPage::NotifyPage(QWidget* parent)
    : BasePage(parent)
{
    setTargetSize(QSize(MIN_WIDTH, BASE_HEIGHT));

    QBoxLayout* layout = setMainLayout('h');
    m_mainLayout->setSpacing(6);
    layout->setSpacing(6);

    m_iconBtn = new SvgButton(this, 36, 16, Svgs::squareIcon());
    m_label = new NotifyLabel(this);
    layout->addWidget(m_iconBtn);
    layout->addWidget(m_label);

    // 单一成员定时器：新消息覆盖时重置计时，避免 singleShot 堆积
    m_exitTimer.setSingleShot(true);
    connect(&m_exitTimer, &QTimer::timeout, this, &NotifyPage::quitPage);
}

void NotifyPage::postMessage(const QString& message, const QString& icon, int duration)
{
    // 取消上一条的自动退出：避免旧定时器在新消息的切换动画期间触发，
    // 直接把尚未显示出来的新消息顶掉
    m_exitTimer.stop();
    m_pending = Pending{message, icon, duration, true};
    // targetSize 必须在 immediateSwitch 之前更新：
    // switchTo 在动画启动时读取它来决定容器目标几何
    setTargetSize(measure(message, icon));
    PageRouter::instance().immediateSwitch(m_pageName);
}

void NotifyPage::onShow()
{
    // 动画透明度暗下瞬间应用待显示内容，并从可见时刻起计自动退出
    if (!m_pending.valid)
        return;
    const QString message = m_pending.message;
    const QString icon = m_pending.icon;
    const int duration = m_pending.duration;
    m_pending = Pending{};

    if (!icon.isEmpty()) {
        m_iconBtn->setSvg(icon);
        m_iconBtn->show();
    } else {
        m_iconBtn->hide();
    }
    m_label->setTextAnimated(message);

    if (duration > 0)
        m_exitTimer.start(duration);
}

void NotifyPage::clearData()
{
    // 提前退出（Esc / 被顶出队列）时丢弃未显示内容并停表
    m_pending = Pending{};
    m_exitTimer.stop();
}

QSize NotifyPage::measure(const QString& message, const QString& icon) const
{
    // 按消息长度计算 targetSize：单行按内容定宽，超宽封顶（不换行，超长部分裁掉）
    const QFontMetrics fm(m_label->font());
    const int iconW = icon.isEmpty() ? 0 : m_iconBtn->width() + m_mainLayout->spacing();
    // 固定开销：容器左右边距 20 + 关闭按钮 36 + 与内容区的间距 6 + 度量余量 15
    constexpr int chrome = 20 + 36 + 6 + 15;

    const int textW = fm.horizontalAdvance(message);
    const int width = qMax(chrome + iconW + textW, MIN_WIDTH);
    return QSize(qMin(width, MAX_WIDTH), BASE_HEIGHT);
}

void NotifyPage::quitPage()
{
    PageRouter::instance().exitSelf(m_pageName);
}

// ==================== 全局通知入口 ====================

void notify(const QString& message, const QString& icon, int duration, bool onlyWhenIdle)
{
    PageRouter& router = PageRouter::instance();
    IPage* page = router.pages.value(QStringLiteral("notify"), nullptr);
    if (!page) {
        qInfo("[notify] 通知页尚未注册，丢弃消息: %ls",
              reinterpret_cast<const wchar_t*>(message.utf16()));
        return;
    }
    if (onlyWhenIdle) {
        const QString current = router.pageQueue.isEmpty()
                                    ? QStringLiteral("home")
                                    : router.pageQueue.first();
        if (current != QLatin1String("home") && current != QLatin1String("notify"))
            return;
    }
    static_cast<NotifyPage*>(page)->postMessage(message, icon, duration);
}
