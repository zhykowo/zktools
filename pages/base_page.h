#pragma once

// 所有页面的基类（对应 pages/base_page.py）
//
// 页面三名称约定：
// - pageId():     代码内注册名（路由标识），子类重写
// - title():      页面标题栏显示文本（setMainLayout('v') 自动取用）
// - moduleName(): 模块中心显示名；空字符串表示不显示在模块中心

#include <QObject>
#include <QSize>
#include <QString>
#include <QWidget>

#include "pages/i_page.h"

class QBoxLayout;
class QHBoxLayout;
class QShortcut;
class SvgButton;

class BasePage : public QWidget, public IPage
{
    Q_OBJECT

public:
    explicit BasePage(QWidget* parent = nullptr);

    // ---- IPage 实现 ----
    QObject* asQObject() override { return this; }
    QWidget* asWidget() override { return this; }
    QString pageName() const override { return m_pageName; }
    void setPageName(const QString& name) override { m_pageName = name; }
    QSize targetSize() const override { return m_targetSize; }
    void setTargetSize(const QSize& size) override { m_targetSize = size; }
    void onShow() override {}
    void clearData() override {}
    QString moduleName() const override { return QString(); }
    QString moduleIcon() const override;
    void onModuleCenterClicked() override;
    bool isVirtual() const override { return false; }
    void addModuleNameChangedCallback(std::function<void()> callback) override;

    // ---- 页面三名称 ----
    virtual QString pageId() const override { return QString(); }
    virtual QString title() const { return QStringLiteral("标题占位符"); }

    // 布局组织：'v' 带标题栏的纵向布局 / 'h' 无标题栏的横向布局，返回内容布局
    QBoxLayout* setMainLayout(char direction, const QString& titleOverride = QString());

    // 模块中心卡片点击行为：默认跳转到本页；子类可重写
    virtual void onBackClicked();

protected:
    void notifyModuleNameChanged() override;
    void setHeader(QBoxLayout* mainLayout, const QString& title);

    QString m_pageName;
    QSize m_targetSize{300, 300};   // 默认大小，子类可以覆盖
    QBoxLayout* m_mainLayout = nullptr;
    QBoxLayout* m_contentLayout = nullptr;
    SvgButton* m_closeBtn = nullptr;
    QShortcut* m_escShortcut = nullptr;

private:
    std::vector<std::function<void()>> m_moduleNameCallbacks;
};
