#include "core/hotkey_manager.h"

#include <QCoreApplication>
#include <QStringList>
#include <QtGlobal>

#include <windows.h>

// Win32 常量
#ifndef MOD_NOREPEAT
#define MOD_NOREPEAT 0x4000
#endif

namespace {

constexpr uint WM_HOTKEY_ = 0x0312;

// 常用特殊按键的虚拟键码 (VK Code)
bool vkFromName(const QString& name, uint* vk)
{
    static const QHash<QString, uint> map = {
        {QStringLiteral("space"), 0x20}, {QStringLiteral("enter"), 0x0D},
        {QStringLiteral("return"), 0x0D}, {QStringLiteral("tab"), 0x09},
        {QStringLiteral("esc"), 0x1B}, {QStringLiteral("escape"), 0x1B},
        {QStringLiteral("backspace"), 0x08}, {QStringLiteral("delete"), 0x2E},
        {QStringLiteral("up"), 0x26}, {QStringLiteral("down"), 0x28},
        {QStringLiteral("left"), 0x25}, {QStringLiteral("right"), 0x27},
        {QStringLiteral("insert"), 0x2D}, {QStringLiteral("home"), 0x24},
        {QStringLiteral("end"), 0x23}, {QStringLiteral("pageup"), 0x21},
        {QStringLiteral("pagedown"), 0x22},
        // 符号键 → VK 码（不能直接用 ASCII，否则会错位成其他按键，如 '.' → VK_DELETE）
        {QStringLiteral("."), 0xBE}, {QStringLiteral(","), 0xBC},
        {QStringLiteral("/"), 0xBF}, {QStringLiteral(";"), 0xBA},
        {QStringLiteral("'"), 0xDE}, {QStringLiteral("["), 0xDB},
        {QStringLiteral("]"), 0xDD}, {QStringLiteral("-"), 0xBD},
        {QStringLiteral("="), 0xBB}, {QStringLiteral("`"), 0xC0},
        {QStringLiteral("\\"), 0xDC},
    };
    // F1 - F24
    if (name.size() >= 2 && name.at(0) == QLatin1Char('f')) {
        bool ok = false;
        const int n = name.mid(1).toInt(&ok);
        if (ok && n >= 1 && n <= 24) {
            *vk = 0x70 + n - 1;
            return true;
        }
    }
    const auto it = map.find(name);
    if (it != map.end()) {
        *vk = it.value();
        return true;
    }
    return false;
}

} // namespace

HotkeyManager& HotkeyManager::instance()
{
    static HotkeyManager mgr;
    return mgr;
}

HotkeyManager::HotkeyManager()
{
    m_appId = GetCurrentProcessId();
}

bool HotkeyManager::parseHotkeyStr(const QString& hotkeyStr, uint* mods, uint* vk) const
{
    uint m = MOD_NOREPEAT;   // 默认加上防重复触发
    uint mainVk = 0;

    const QStringList parts = hotkeyStr.toLower().remove(QLatin1Char(' '))
                                  .split(QLatin1Char('+'));
    for (const QString& part : parts) {
        if (part.isEmpty())
            continue;   // 容忍 "ctrl++a" 之类的空段
        if (part == QLatin1String("ctrl") || part == QLatin1String("control")) {
            m |= MOD_CONTROL;
        } else if (part == QLatin1String("alt")) {
            m |= MOD_ALT;
        } else if (part == QLatin1String("shift")) {
            m |= MOD_SHIFT;
        } else if (part == QLatin1String("win") || part == QLatin1String("cmd")) {
            m |= MOD_WIN;
        } else {
            uint candidate = 0;
            if (vkFromName(part, &candidate)) {
                if (mainVk != 0) {
                    qWarning("[HotkeyManager] 快捷键 '%ls' 包含多个主按键",
                             reinterpret_cast<const wchar_t*>(hotkeyStr.utf16()));
                    return false;
                }
                mainVk = candidate;
            } else if (part.size() == 1 && part.at(0).isLetterOrNumber()) {
                if (mainVk != 0) {
                    qWarning("[HotkeyManager] 快捷键 '%ls' 包含多个主按键",
                             reinterpret_cast<const wchar_t*>(hotkeyStr.utf16()));
                    return false;
                }
                // 字母或数字的 ASCII 码与其 VK 码一致
                mainVk = part.at(0).toUpper().toLatin1();
            } else {
                qWarning("[HotkeyManager] 无法识别的按键名称: %ls",
                         reinterpret_cast<const wchar_t*>(part.utf16()));
                return false;
            }
        }
    }

    if (mainVk == 0) {
        qWarning("[HotkeyManager] 快捷键 '%ls' 缺少主按键！",
                 reinterpret_cast<const wchar_t*>(hotkeyStr.utf16()));
        return false;
    }
    *mods = m;
    *vk = mainVk;
    return true;
}

uint HotkeyManager::allocHotkeyId()
{
    // GlobalAddAtom 生成全局唯一原子 ID，避免与其他进程注册的 RegisterHotKey ID 冲突
    const QString name = QStringLiteral("CppDiHotkey_%1_%2").arg(m_appId).arg(m_counter);
    ++m_counter;
    const ATOM atom = GlobalAddAtomW(reinterpret_cast<const wchar_t*>(name.utf16()));
    if (atom != 0) {
        m_atomIds.insert(atom);
        return atom;
    }
    // 原子表已满等异常情况：退回进程内自增 ID（仍有极小概率与其他进程冲突）
    return m_counter - 1;
}

void HotkeyManager::freeHotkeyId(uint id)
{
    if (m_atomIds.remove(id))
        GlobalDeleteAtom(static_cast<ATOM>(id));
}

void HotkeyManager::releaseAllModifiers()
{
    // 触发任何热键前，向系统广播所有修饰键的抬起事件，保证后续按键模拟时状态干净
    constexpr WORD modVks[] = {VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN};
    for (WORD vk : modVks)
        keybd_event(vk, 0, KEYEVENTF_KEYUP, 0);
}

bool HotkeyManager::nativeEventFilter(const QByteArray& eventType, void* message, qintptr*)
{
    if (eventType != QByteArrayLiteral("windows_generic_MSG"))
        return false;

    const MSG* msg = static_cast<const MSG*>(message);
    if (msg->message != WM_HOTKEY_)
        return false;

    // 1. 触发任何快捷键前，先自动重置/释放所有修饰键状态
    releaseAllModifiers();

    // 2. 分发回调（主线程同步执行，保持 False 不吞消息）
    const uint hotkeyId = static_cast<uint>(msg->wParam);
    const auto it = m_idMap.find(hotkeyId);
    if (it != m_idMap.end() && it.value().second)
        it.value().second();
    return false;
}

// ================= 公开 API =================

bool HotkeyManager::registerHotkey(const QString& hotkeyStr, std::function<void()> callback)
{
    if (!m_installed) {
        qWarning("[HotkeyManager] register 失败：监听未启动，请先调用 start()（快捷键 '%ls'）",
                 reinterpret_cast<const wchar_t*>(hotkeyStr.utf16()));
        return false;
    }

    const QString formatted = hotkeyStr.toLower().remove(QLatin1Char(' '));
    uint mods = 0, vk = 0;
    if (!parseHotkeyStr(formatted, &mods, &vk))
        return false;

    if (m_hotkeys.contains(formatted)) {
        qWarning("[HotkeyManager] 快捷键 '%ls' 已注册，请先注销再重新注册",
                 reinterpret_cast<const wchar_t*>(hotkeyStr.utf16()));
        return false;
    }

    const uint hotkeyId = allocHotkeyId();
    if (RegisterHotKey(nullptr, static_cast<int>(hotkeyId), mods, vk)) {
        m_hotkeys.insert(formatted, hotkeyId);
        m_idMap.insert(hotkeyId, {formatted, std::move(callback)});
        qInfo("[HotkeyManager] 已成功注册并独占拦截快捷键: %ls",
              reinterpret_cast<const wchar_t*>(formatted.utf16()));
        return true;
    }

    freeHotkeyId(hotkeyId);
    qWarning("[HotkeyManager] 快捷键 %ls 注册失败，可能已被系统或其他软件占用！",
             reinterpret_cast<const wchar_t*>(formatted.utf16()));
    return false;
}

void HotkeyManager::unregisterHotkey(const QString& hotkeyStr)
{
    const QString formatted = hotkeyStr.toLower().remove(QLatin1Char(' '));
    const auto it = m_hotkeys.find(formatted);
    if (it != m_hotkeys.end()) {
        const uint hotkeyId = it.value();
        m_hotkeys.erase(it);
        m_idMap.remove(hotkeyId);
        UnregisterHotKey(nullptr, static_cast<int>(hotkeyId));
        freeHotkeyId(hotkeyId);
        qInfo("[HotkeyManager] 已注销快捷键: %ls",
              reinterpret_cast<const wchar_t*>(formatted.utf16()));
    }
}

void HotkeyManager::start()
{
    if (m_installed)
        return;
    QCoreApplication* app = QCoreApplication::instance();
    if (!app) {
        qWarning("[HotkeyManager] start 失败：尚未创建 QCoreApplication/QApplication");
        return;
    }
    app->installNativeEventFilter(this);
    m_installed = true;
    qInfo("[HotkeyManager] 原生独占热键监听已挂载到 Qt 事件循环...");
}

void HotkeyManager::stop()
{
    if (!m_installed)
        return;
    if (QCoreApplication* app = QCoreApplication::instance())
        app->removeNativeEventFilter(this);
    m_installed = false;

    const QList<uint> ids = m_idMap.keys();
    for (uint id : ids) {
        UnregisterHotKey(nullptr, static_cast<int>(id));
        freeHotkeyId(id);
    }
    m_idMap.clear();
    m_hotkeys.clear();
    qInfo("[HotkeyManager] 监听已安全停止。");
}
