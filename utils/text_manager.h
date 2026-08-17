#pragma once

// 取词管理单例（对应 utils/text_manager.py）
//
// Python 版依赖 uiautomation 库，C++ 版直接使用 Windows 原生 UI Automation COM API：
// - getSelectedText():     聚焦控件的 TextPattern 当前选区（不污染剪贴板）
// - copySelectedText():    优先 UIA 直读；不支持文本模式的控件回退为模拟 Ctrl+C 后读剪贴板

#include <QObject>
#include <QString>

struct IUIAutomation;

class TextManager : public QObject
{
    Q_OBJECT

public:
    static TextManager& instance();

    // 最近一次选中文本与时间戳（performance 计数，秒），供翻译页 onShow 判断新鲜度
    QString selectedText;
    double selectionTime = 0.0;

    // 最近一次剪贴板文本与时间戳
    QString clipboardText;
    double copyTime = 0.0;

    // 读取当前选中文本；成功时更新 selectedText/selectionTime 并返回文本，失败返回空串
    QString getSelectedText();

    // 复制当前选中文本（供一键翻译使用）：UIA 直读优先，Ctrl+C 回退，带短重试
    QString copySelectedText(int retries = 5, int delayMs = 50);

    // 单调时钟（performance 计数，秒）
    static double nowSec();

private:
    explicit TextManager();

    IUIAutomation* m_uia = nullptr;   // 惰性创建的 UIA COM 接口
};
