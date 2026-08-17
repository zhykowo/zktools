#pragma once

// 设置页（对应 pages/setting_page.py）：占位页面

#include "pages/base_page.h"
#include "resources/svgs.h"

class SettingPage : public BasePage
{
    Q_OBJECT

public:
    explicit SettingPage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("setting"); }
    QString title() const override { return QStringLiteral("Setting"); }
    QString moduleIcon() const override { return Svgs::settingsIcon(); }
};
