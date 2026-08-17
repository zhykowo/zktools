#pragma once

// 触摸板控制模块（对应 pages/touchpad_ctl_page.py）
//
// 线程模型：
// - 热键回调运行在 HotkeyManager 的 Qt 主线程分发中，只做状态裁决并发射信号；
// - 阻塞的开关操作（runSwitchTouchpad）放在独立工作线程执行，避免卡住事件循环；
// - 所有 UI 更新都通过信号回到主线程完成。
//
// 本模块无独立界面（继承 VirtualPage"假页面"），状态展示统一由 notify() 弹出；
// 模块中心卡片文本按状态动态提供（"TchPad Off"/"TchPad On"）。

#include <QMutex>
#include <QObject>
#include <QString>

#include "pages/notify_page.h"
#include "resources/svgs.h"

enum class TouchpadState
{
    Disabled,   // "Disabled"
    Enabled,    // "Enabled"
    Disabling,  // "Disabling"
    Enabling,   // "Enabling"
};

QString touchpadStateToString(TouchpadState state);
bool touchpadStateIsTransitioning(TouchpadState state);

// 触摸板开关控制器：线程安全的状态裁决 + 后台执行开关操作（模块级共享单例）
class TouchpadController : public QObject
{
    Q_OBJECT

public:
    static TouchpadController& instance();

    TouchpadState state() const;

    // 热键回调入口（主线程分发）。非过渡态时发起一次切换。
    void requestSwitch();

signals:
    // 状态变化信号（在主线程消费）；跨线程发射自动排队
    void stateChanged(int newState);

private:
    explicit TouchpadController(QObject* parent = nullptr);

    static TouchpadState readInitialState();

    void performSwitch(bool enable, TouchpadState finalState, TouchpadState previousState);

    mutable QMutex m_lock;                  // 保护 m_state 的跨线程访问
    TouchpadState m_state = TouchpadState::Disabled;
};

class TouchpadCtlPage : public VirtualPage
{
    Q_OBJECT

public:
    explicit TouchpadCtlPage(QObject* parent = nullptr);

    QString pageId() const override { return QStringLiteral("switch_touchpad"); }
    QString moduleIcon() const override { return Svgs::touchpadIcon(); }

    // 模块中心显示名：按当前触摸板状态动态返回
    QString moduleName() const override;

    // 模块中心卡片点击：直接触发一次触摸板切换（与全局热键行为一致）
    void onModuleCenterClicked() override;

private slots:
    void onStateChanged(int newState);

private:
    void registerHotkeys();
    void onTestHotkey();

    static QString moduleCenterText(TouchpadState state);
};
