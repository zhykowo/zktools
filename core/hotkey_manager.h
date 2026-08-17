#pragma once

// 基于 Windows 原生 RegisterHotKey 的热键管理器（对应 core/hotkey_manager.py，Qt 事件循环版）
//
// 通过 QAbstractNativeEventFilter 挂到 Qt 事件循环上拦截 WM_HOTKEY：
// - registerHotkey() 必须在 Qt 主线程调用（WM_HOTKEY 只投递到注册线程的消息队列）；
// - 回调在 Qt 事件循环线程同步执行，只应做轻量状态裁决，不得阻塞 UI。

#include <QAbstractNativeEventFilter>
#include <QByteArray>
#include <QHash>
#include <QObject>
#include <QSet>
#include <QString>

#include <functional>

class HotkeyManager : public QObject, public QAbstractNativeEventFilter
{
    Q_OBJECT

public:
    static HotkeyManager& instance();

    // 动态注册快捷键（如 "ctrl+alt+a"），系统级独占拦截；同步返回注册结果
    bool registerHotkey(const QString& hotkeyStr, std::function<void()> callback);

    // 动态删除快捷键
    void unregisterHotkey(const QString& hotkeyStr);

    // 将热键监听挂到 Qt 事件循环上（幂等）
    void start();

    // 停止监听并注销所有快捷键
    void stop();

    bool nativeEventFilter(const QByteArray& eventType, void* message, qintptr* result) override;

private:
    explicit HotkeyManager();

    // 解析 "ctrl+alt+a" -> (Win32 修饰键, VK 码)；失败返回 false
    bool parseHotkeyStr(const QString& hotkeyStr, uint* mods, uint* vk) const;

    uint allocHotkeyId();      // GlobalAddAtom 优先，失败退回进程内自增
    void freeHotkeyId(uint id);
    void releaseAllModifiers();  // 触发热键时广播修饰键抬起，清理系统按键状态

    QHash<QString, uint> m_hotkeys;        // "ctrl+alt+a" -> hotkey_id
    QHash<uint, std::pair<QString, std::function<void()>>> m_idMap;  // id -> (hotkey, callback)
    uint m_counter = 1;
    unsigned long m_appId = 0;             // GetCurrentProcessId
    QSet<uint> m_atomIds;                  // GlobalAddAtom 分配的原子（注销时释放）
    bool m_installed = false;
};
