#include "pages/clipboard_ctl_page.h"

#include "resources/svgs.h"
#include "utils/clipboard_monitor.h"

ClipboardCtlPage::ClipboardCtlPage(QObject* parent)
    : VirtualPage(parent)
{
    // 连接依赖 ClipboardMonitor 已初始化（main 启动顺序保证）
    connect(&ClipboardMonitor::instance(), &ClipboardMonitor::cbChanged,
            this, &ClipboardCtlPage::onClipboardChanged);
}

void ClipboardCtlPage::onClipboardChanged(const QString&)
{
    notify(QStringLiteral("Copied!"), Svgs::clipboardIcon(), 1500, /*onlyWhenIdle=*/true);
}
