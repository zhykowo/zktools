#pragma once

// 全局鼠标悬停事件过滤器（对应 utils/mouse_tracker.py）：调试用，
// debugEnabled 开启时打印鼠标进入的控件，默认关闭（等价于返回 False 直通）。

#include <QObject>

class QEvent;
class QObject;

class MouseHoverEventFilter : public QObject
{
    Q_OBJECT

public:
    explicit MouseHoverEventFilter(bool debugEnabled = true, QObject* parent = nullptr);

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    bool m_debugEnabled;
    QObject* m_lastHoveredWidget = nullptr;
};
