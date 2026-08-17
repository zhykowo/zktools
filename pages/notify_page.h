#pragma once

// 全局通知页（对应 pages/notify_page.py）
//
// - NotifyPage：所有瞬时消息提醒的统一出口，由 main 注册一次（全局单例页面）；
// - VirtualPage：无界面模块的 BasePage 兼容替代（"假页面"），触摸板开关、剪贴板
//   变化等纯后台模块继承它注册进页面池，状态展示统一走 notify()；
// - notify()：全局通知入口，任何模块调用即弹出通知（须在主线程调用）。
//
// 行为约定（与 Python 版一致）：
// - notify() 只登记待显示内容并把本页立即切换到队首；文字/图标的真正应用发生在
//   切换动画透明度暗下瞬间的 onShow()；
// - 消息冲突：新消息直接覆盖旧消息，旧消息的自动退出定时器在登记时即被取消；
// - duration <= 0 表示常驻，直到被下一条消息覆盖；
// - 文本由 NotifyLabel 渲染：动态行渐变（白 ↔ 强调色行波）+ 逐字冒出动画。

#include <QColor>
#include <QElapsedTimer>
#include <QLinearGradient>
#include <QObject>
#include <QPointer>
#include <QString>
#include <QTextLayout>
#include <QTimer>
#include <QVector>
#include <QWidget>

#include "pages/base_page.h"

class SvgButton;

// ==================== VirtualPage ====================

class VirtualPage : public QObject, public IPage
{
    Q_OBJECT

public:
    explicit VirtualPage(QObject* parent = nullptr);

    QObject* asQObject() override { return this; }
    QString pageName() const override { return m_pageName; }
    void setPageName(const QString& name) override { m_pageName = name; }
    // 无界面页面没有目标尺寸（dispatch 不会对虚拟页面发起切换）
    QSize targetSize() const override { return {}; }
    void setTargetSize(const QSize&) override {}
    bool isVirtual() const override { return true; }
    QString moduleName() const override { return QString(); }
    QString moduleIcon() const override;
    void onModuleCenterClicked() override {}
    void addModuleNameChangedCallback(std::function<void()> callback) override;

protected:
    void notifyModuleNameChanged() override;

    QString m_pageName;

private:
    std::vector<std::function<void()>> m_moduleNameCallbacks;
};

// ==================== NotifyLabel ====================

class NotifyLabel : public QWidget
{
    Q_OBJECT

public:
    explicit NotifyLabel(QWidget* parent = nullptr);

    QString text() const { return m_text; }

    // 设置文本并重置逐字动画时钟（同文本重复设置也会重播动画）
    void setTextAnimated(const QString& text);

protected:
    void showEvent(QShowEvent* event) override;
    void hideEvent(QHideEvent* event) override;
    void paintEvent(QPaintEvent* event) override;

private:
    // 逐码点拆分文本：(UTF-16 码元起始位置, 码点字符串)。
    // Qt 文本坐标（QTextLine 的 textStart/textLength/cursorToX）按 UTF-16 码元计数，
    // emoji 等增补平面字符占两个码元，须换算后才能对上 Qt 的行内位置。
    struct CharInfo
    {
        int utf16Start;
        QString ch;
    };
    static QVector<CharInfo> splitChars(const QString& text);

    // 按给定宽度布局文本（不换行，单行；测量与绘制共用同一逻辑）
    void ensureLayout();

    // 第 k 个字符的动画进度 [0,1]
    double charProgress(int k, int n, double span, double t) const;
    static double outCubic(double p);
    double outBack(double p) const;

    // 横跨一行宽度的动态渐变：白 ↔ 强调色行波，相位随时间自左向右扫过
    QLinearGradient lineGradient(double lineWidth, double phase) const;

    QString m_text;
    QVector<CharInfo> m_chars;
    QTextLayout m_layout;      // QTextLine 依附其存活，须持有
    QVector<QTextLine> m_lines;
    int m_layoutWidth = -1;

    QElapsedTimer m_clock;
    QTimer m_timer;
    QColor m_waveColor;

    // ---- 逐字动画参数（可按观感微调） ----
    static constexpr int CHAR_DURATION = 210;     // 单字动画时长 ms（恒定）
    static constexpr double DROP_PX = 10.0;       // 单字起始向下偏移量
    static constexpr double BACK_OVERSHOOT = 1.2; // 位移回弹强度（标准 OutBack 为 1.0）
    static constexpr double ACCEL_P = 1.8;        // 启动时刻曲线指数，>1 时相邻间隔递减
    static constexpr int SPAN_BASE = 260;         // 首末字符启动间隔：基础时长 ms
    static constexpr int SPAN_PER_CHAR = 9;       // 每个字符追加的间隔 ms
    static constexpr int SPAN_MIN = 320;
    static constexpr int SPAN_MAX = 900;
    static constexpr int LINE_SPACING = 2;        // 额外行距 px

    // ---- 行渐变参数 ----
    static constexpr int WAVE_PERIOD = 2600;      // 渐变行波循环周期 ms
    static constexpr int WAVE_STOPS = 12;         // 每行渐变的采样档数
    static constexpr double WAVE_STRENGTH = 0.85; // 行波峰值处的强调色混合上限
};

// ==================== NotifyPage ====================

class NotifyPage : public BasePage
{
    Q_OBJECT

public:
    explicit NotifyPage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("notify"); }
    QString title() const override { return QStringLiteral("Notify"); }

    // 登记一条消息并立即切入本页（由 notify() 调用，仅限主线程）
    void postMessage(const QString& message, const QString& icon, int duration);

    void onShow() override;
    void clearData() override;

    static constexpr int MAX_WIDTH = 430;    // 主窗口 450 - 容器左右边距 10 * 2
    static constexpr int MIN_WIDTH = 160;
    static constexpr int BASE_HEIGHT = 50;   // 单行消息高度

private slots:
    void quitPage();

private:
    // 按消息长度计算 targetSize：单行按内容定宽，超宽封顶（不换行，超长部分裁掉）
    QSize measure(const QString& message, const QString& icon) const;

    SvgButton* m_iconBtn = nullptr;
    NotifyLabel* m_label = nullptr;

    // 待显示内容 (message, icon, duration)，在动画暗下瞬间的 onShow 消费
    struct Pending
    {
        QString message;
        QString icon;
        int duration = 0;
        bool valid = false;
    };
    Pending m_pending;

    // 单一成员定时器：新消息覆盖时重置计时，避免 singleShot 堆积
    QTimer m_exitTimer;
};

// ==================== 全局通知入口 ====================

// 任何模块调用即弹出通知（须在主线程调用）：
// - icon 为空串不显示图标；duration <= 0 表示常驻，直到被下一条消息覆盖；
// - onlyWhenIdle=true 时，若当前正显示 home/通知页以外的页面则丢弃消息
void notify(const QString& message, const QString& icon = QString(), int duration = 1500,
            bool onlyWhenIdle = false);
