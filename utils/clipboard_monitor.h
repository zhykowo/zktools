#pragma once

// 剪贴板监听单例（对应 utils/clipboard_monitor.py）：系统剪贴板内容变化时发出 cbChanged

#include <QObject>
#include <QString>

class ClipboardMonitor : public QObject
{
    Q_OBJECT

public:
    static ClipboardMonitor& instance();

signals:
    void cbChanged(const QString& text);

private:
    explicit ClipboardMonitor();
};
