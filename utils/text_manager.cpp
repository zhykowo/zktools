#include "utils/text_manager.h"

#include "utils/clipboard_monitor.h"

#include <QClipboard>
#include <QGuiApplication>
#include <QThread>
#include <QtGlobal>

#include <chrono>
#include <windows.h>

// UIAutomation.h 依赖 windows.h；MinGW 的该头文件不带 C++ 保护，包在 extern "C" 外层
#include <objbase.h>
#include <uiautomation.h>

static double perfNow()
{
    using namespace std::chrono;
    return duration_cast<duration<double>>(steady_clock::now().time_since_epoch()).count();
}

TextManager& TextManager::instance()
{
    static TextManager mgr;
    return mgr;
}

TextManager::TextManager()
{
    selectionTime = perfNow();
    copyTime = selectionTime;

    if (SUCCEEDED(CoCreateInstance(CLSID_CUIAutomation8, nullptr, CLSCTX_INPROC_SERVER,
                                   IID_PPV_ARGS(&m_uia)))) {
        // 创建成功
    } else {
        m_uia = nullptr;
        qWarning("[text_manager] UI Automation 初始化失败，取词功能将回退 Ctrl+C");
    }

    connect(&ClipboardMonitor::instance(), &ClipboardMonitor::cbChanged,
            this, [this](const QString& text) {
                clipboardText = text;
                copyTime = perfNow();
            });
}

double TextManager::nowSec()
{
    return perfNow();
}

QString TextManager::getSelectedText()
{
    if (!m_uia)
        return QString();

    IUIAutomationElement* element = nullptr;
    if (FAILED(m_uia->GetFocusedElement(&element)) || !element)
        return QString();

    QString result;
    IUIAutomationTextPattern* textPattern = nullptr;
    if (SUCCEEDED(element->GetCurrentPatternAs(UIA_TextPatternId, IID_PPV_ARGS(&textPattern)))
        && textPattern) {
        IUIAutomationTextRangeArray* ranges = nullptr;
        if (SUCCEEDED(textPattern->GetSelection(&ranges)) && ranges) {
            IUIAutomationTextRange* range = nullptr;
            if (SUCCEEDED(ranges->GetElement(0, &range)) && range) {
                BSTR text = nullptr;
                if (SUCCEEDED(range->GetText(-1, &text))) {
                    result = QString::fromWCharArray(text);
                    SysFreeString(text);
                }
                range->Release();
            }
            ranges->Release();
        }
        textPattern->Release();
    }
    element->Release();

    if (!result.isNull()) {
        selectedText = result;
        selectionTime = perfNow();
    }
    return result;
}

QString TextManager::copySelectedText(int retries, int delayMs)
{
    // 1. 优先直接读取选中文本，避免覆盖用户剪贴板
    const QString text = getSelectedText();
    if (!text.isEmpty())
        return text;

    // 2. 回退方案：模拟 Ctrl+C 后从剪贴板读取
    INPUT inputs[4]{};
    inputs[0].type = INPUT_KEYBOARD;
    inputs[0].ki.wVk = VK_CONTROL;
    inputs[1].type = INPUT_KEYBOARD;
    inputs[1].ki.wVk = 'C';
    inputs[2].type = INPUT_KEYBOARD;
    inputs[2].ki.wVk = 'C';
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP;
    inputs[3].type = INPUT_KEYBOARD;
    inputs[3].ki.wVk = VK_CONTROL;
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP;
    if (SendInput(4, inputs, sizeof(INPUT)) != 4) {
        qWarning("[text_manager] 模拟 Ctrl+C 失败");
        return QString();
    }

    // 剪贴板内容更新是异步的，做几次短重试
    QClipboard* clipboard = QGuiApplication::clipboard();
    for (int i = 0; i < retries; ++i) {
        const QString clipboardTextNow = clipboard->text();
        if (!clipboardTextNow.isEmpty()) {
            selectedText = clipboardTextNow;
            selectionTime = perfNow();
            return clipboardTextNow;
        }
        QThread::msleep(delayMs);
    }

    qInfo("[text_manager] 未获取到选中文本");
    return QString();
}
