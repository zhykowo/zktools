#pragma once

// 剪贴板模块（对应 pages/clipboard_ctl_page.py）：无界面"假页面"。
// 剪贴板变化时经全局通知页弹出 "Copied!" 提醒；
// 仅当当前处于 home/通知页时提醒，不打断使用中的页面。

#include "pages/notify_page.h"

class ClipboardCtlPage : public VirtualPage
{
    Q_OBJECT

public:
    explicit ClipboardCtlPage(QObject* parent = nullptr);

    QString pageId() const override { return QStringLiteral("clipboard"); }
    // 剪贴板变化通知的模块入口：无界面，不显示在模块中心（moduleName 保持为空）

private slots:
    void onClipboardChanged(const QString& text);
};
