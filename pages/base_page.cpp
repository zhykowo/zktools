#include "pages/base_page.h"

#include "core/page_router.h"
#include "core/window_manager.h"
#include "resources/colors.h"
#include "resources/svgs.h"
#include "widgets/svg_button.h"

#include <QApplication>
#include <QBoxLayout>
#include <QFont>
#include <QHBoxLayout>
#include <QKeySequence>
#include <QLabel>
#include <QPalette>
#include <QShortcut>
#include <QVBoxLayout>

BasePage::BasePage(QWidget* parent)
    : QWidget(parent)
{
    // 创建页面级 Esc 快捷键
    m_escShortcut = new QShortcut(QKeySequence(Qt::Key_Escape), this);
    connect(m_escShortcut, &QShortcut::activated, this, &BasePage::onBackClicked);

    // 全局关闭按钮
    m_closeBtn = new SvgButton(this, 36, 20, Svgs::closeIcon(), Colors::danger(), true);
    connect(m_closeBtn, &SvgButton::clicked, qApp, &QCoreApplication::quit);
}

QString BasePage::moduleIcon() const
{
    return Svgs::squareIcon();
}

void BasePage::onModuleCenterClicked()
{
    // 模块中心卡片点击行为：默认跳转到本页；子类可重写
    PageRouter::instance().immediateSwitch(m_pageName);
}

void BasePage::addModuleNameChangedCallback(std::function<void()> callback)
{
    m_moduleNameCallbacks.push_back(std::move(callback));
}

void BasePage::notifyModuleNameChanged()
{
    for (const auto& cb : m_moduleNameCallbacks)
        cb();
}

QBoxLayout* BasePage::setMainLayout(char direction, const QString& titleOverride)
{
    if (direction == 'v') {
        auto* mainLayout = new QVBoxLayout(this);
        mainLayout->setContentsMargins(0, 8, 0, 8);
        mainLayout->setSpacing(8);
        setHeader(mainLayout, titleOverride.isEmpty() ? title() : titleOverride);
        auto* contentLayout = new QVBoxLayout();
        mainLayout->addLayout(contentLayout);
        m_mainLayout = mainLayout;
        m_contentLayout = contentLayout;

    } else if (direction == 'h') {
        auto* mainLayout = new QHBoxLayout(this);
        mainLayout->setContentsMargins(0, 0, 0, 0);
        auto* contentLayout = new QHBoxLayout();
        mainLayout->addLayout(contentLayout);
        mainLayout->addWidget(m_closeBtn);
        m_mainLayout = mainLayout;
        m_contentLayout = contentLayout;
    }
    return m_contentLayout;
}

void BasePage::setHeader(QBoxLayout* mainLayout, const QString& title)
{
    auto* headerLayout = new QHBoxLayout();
    headerLayout->setContentsMargins(0, 0, 0, 0);
    headerLayout->setSpacing(6);
    // 返回按钮 + 页面标题
    auto* headerLeft = new QHBoxLayout();
    // 拖拽按钮 + 全局关闭按钮
    auto* headerRight = new QHBoxLayout();

    auto* titleLabel = new QLabel(title, this);
    QFont titleFont = titleLabel->font();
    titleFont.setPixelSize(13);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);
    QPalette titlePalette = titleLabel->palette();
    titlePalette.setColor(QPalette::ColorRole::WindowText, Colors::white());
    titleLabel->setPalette(titlePalette);

    auto* backBtn = new SvgButton(this, 36, 20, Svgs::arrowLeftIcon());
    connect(backBtn, &SvgButton::clicked, this, &BasePage::onBackClicked);

    auto* dragBtn = new SvgButton(this, 36, 20, Svgs::dragIcon());
    emit DragBus::instance().registerDragHandleRequested(dragBtn);

    headerLeft->addWidget(backBtn);
    headerRight->addWidget(dragBtn);
    headerRight->addWidget(m_closeBtn);
    headerLeft->addWidget(titleLabel);
    headerLeft->addStretch();

    headerLayout->addLayout(headerLeft);
    headerLayout->addLayout(headerRight);
    mainLayout->addLayout(headerLayout);
}

void BasePage::onBackClicked()
{
    PageRouter::instance().exitSelf(m_pageName);
}
