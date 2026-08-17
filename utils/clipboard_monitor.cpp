#include "utils/clipboard_monitor.h"

#include <QClipboard>
#include <QGuiApplication>

ClipboardMonitor& ClipboardMonitor::instance()
{
    static ClipboardMonitor monitor;
    return monitor;
}

ClipboardMonitor::ClipboardMonitor()
{
    QClipboard* clipboard = QGuiApplication::clipboard();
    connect(clipboard, &QClipboard::dataChanged, this, [this, clipboard]() {
        const QString text = clipboard->text();
        if (!text.isEmpty())
            emit cbChanged(text);
    });
}
