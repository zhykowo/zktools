#include "pages/touchpad_ctl_page.h"

#include "core/hotkey_manager.h"
#include "resources/constants.h"
#include "resources/svgs.h"
#include "utils/switch_touchpad.h"

#include <QThread>
#include <QtGlobal>

QString touchpadStateToString(TouchpadState state)
{
    switch (state) {
    case TouchpadState::Disabled:  return QStringLiteral("Disabled");
    case TouchpadState::Enabled:   return QStringLiteral("Enabled");
    case TouchpadState::Disabling: return QStringLiteral("Disabling");
    case TouchpadState::Enabling:  return QStringLiteral("Enabling");
    }
    return QStringLiteral("Disabled");
}

bool touchpadStateIsTransitioning(TouchpadState state)
{
    return state == TouchpadState::Disabling || state == TouchpadState::Enabling;
}

// ==================== TouchpadController ====================

TouchpadController& TouchpadController::instance()
{
    static TouchpadController controller;
    return controller;
}

TouchpadController::TouchpadController(QObject* parent)
    : QObject(parent)
{
    // 启动时读取系统真实状态，避免初始显示与实际情况不一致
    m_state = readInitialState();
}

TouchpadState TouchpadController::readInitialState()
{
    // 查询失败时回退为禁用（与旧默认行为一致）
    const std::optional<bool> enabled = SwitchTouchpad::getTouchpadStatus();
    if (!enabled.has_value()) {
        qInfo("[TouchpadController] 读取触摸板状态失败,按禁用状态初始化");
        return TouchpadState::Disabled;
    }
    return *enabled ? TouchpadState::Enabled : TouchpadState::Disabled;
}

TouchpadState TouchpadController::state() const
{
    QMutexLocker locker(&m_lock);
    return m_state;
}

void TouchpadController::requestSwitch()
{
    bool enable = false;
    TouchpadState intermediate{}, finalState{}, previousState{};
    {
        QMutexLocker locker(&m_lock);
        if (touchpadStateIsTransitioning(m_state))
            return;   // 切换中的中间态忽略新的切换请求
        previousState = m_state;
        if (previousState == TouchpadState::Enabled) {
            intermediate = TouchpadState::Disabling;
            finalState = TouchpadState::Disabled;
            enable = false;
        } else {
            intermediate = TouchpadState::Enabling;
            finalState = TouchpadState::Enabled;
            enable = true;
        }
        m_state = intermediate;
    }

    // 通知主线程：弹出"切换中"常驻通知
    emit stateChanged(int(intermediate));

    // 阻塞操作放入工作线程，热键分发立即返回
    QThread* worker = QThread::create(
        [this, enable, finalState, previousState]() {
            performSwitch(enable, finalState, previousState);
        });
    connect(worker, &QThread::finished, worker, &QObject::deleteLater);
    worker->start();
}

void TouchpadController::performSwitch(bool enable, TouchpadState finalState,
                                       TouchpadState /*previousState*/)
{
    // 工作线程：执行开关操作，完成后把结果送回主线程。
    // 与 Python 版一致：设备枚举/提权失败在 runSwitchTouchpad 内部兜底打印，
    // 状态机正常推进到最终状态（Python 亦仅在异常时回退，而这里不会抛异常）。
    SwitchTouchpad::runSwitchTouchpad(enable);

    {
        QMutexLocker locker(&m_lock);
        m_state = finalState;
    }
    emit stateChanged(int(m_state));
}

// ==================== TouchpadCtlPage ====================

TouchpadCtlPage::TouchpadCtlPage(QObject* parent)
    : VirtualPage(parent)
{
    // 使用模块级共享控制器：module_center_page 也订阅它的状态变化
    connect(&TouchpadController::instance(), &TouchpadController::stateChanged,
            this, &TouchpadCtlPage::onStateChanged);

    registerHotkeys();
}

void TouchpadCtlPage::registerHotkeys()
{
    HotkeyManager& hotkeys = HotkeyManager::instance();
    hotkeys.start();

    const QString testHotkey = AppConfig::instance().string(
        QStringLiteral("touchpad_ctl.hotkeys.test"), QStringLiteral("ctrl+alt+a"));
    const QString switchHotkey = AppConfig::instance().string(
        QStringLiteral("touchpad_ctl.hotkeys.switch"), QStringLiteral("ctrl+shift+b"));

    const bool testOk = hotkeys.registerHotkey(
        testHotkey, [this]() { onTestHotkey(); });
    const bool switchOk = hotkeys.registerHotkey(
        switchHotkey, []() { TouchpadController::instance().requestSwitch(); });

    if (!testOk || !switchOk) {
        qWarning("[TouchpadCtlPage] 警告：部分触控板控制热键注册失败，相关快捷键将不可用");
    }
}

void TouchpadCtlPage::onTestHotkey()
{
    // 测试热键回调：仅打印，不触碰 UI
    qInfo("\n[TouchpadCtlPage] 触发了测试动作 (Ctrl + Alt + A)");
}

QString TouchpadCtlPage::moduleName() const
{
    return moduleCenterText(TouchpadController::instance().state());
}

void TouchpadCtlPage::onModuleCenterClicked()
{
    TouchpadController::instance().requestSwitch();
}

QString TouchpadCtlPage::moduleCenterText(TouchpadState state)
{
    // 关闭显示 TchPad Off，开启显示 TchPad On
    if (state == TouchpadState::Disabled || state == TouchpadState::Enabling)
        return QStringLiteral("TchPad Off");
    if (state == TouchpadState::Enabled || state == TouchpadState::Disabling)
        return QStringLiteral("TchPad On");
    return QStringLiteral("TchPad Off");   // 未知状态兜底
}

void TouchpadCtlPage::onStateChanged(int newStateInt)
{
    const TouchpadState newState = static_cast<TouchpadState>(newStateInt);
    // 切换中：常驻通知（不会被自动退出，只会被完成态覆盖）
    // 切换完成：覆盖"切换中"通知并展示最终状态，3 秒后自动退出
    notify(QStringLiteral("TouchPad %1").arg(touchpadStateToString(newState)),
           Svgs::touchpadIcon(),
           touchpadStateIsTransitioning(newState) ? 0 : 3000);
    // 名称随状态变化，通知 module_center_page 实时刷新卡片
    notifyModuleNameChanged();
}
