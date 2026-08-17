#include "pages/module_center_page.h"

#include "core/page_router.h"
#include "pages/i_page.h"
#include "resources/colors.h"
#include "resources/svgs.h"
#include "widgets/svg_button.h"

#include <QFont>
#include <QGridLayout>
#include <QLabel>
#include <QPalette>
#include <QVBoxLayout>
#include <QWidget>

// ==================== ModuleCard ====================

ModuleCard::ModuleCard(const QString& name, const QString& iconData, QWidget* parent)
    : QWidget(parent)
{
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 2, 0, 2);
    layout->setSpacing(4);
    layout->setAlignment(Qt::AlignmentFlag::AlignCenter);

    // 小图标 (22x22 黄金比例大小)
    iconBtn = new SvgButton(this, 36, 22,
                             iconData.isEmpty() ? Svgs::squareIcon() : iconData);

    // 模块名称
    label = new QLabel(name, this);
    label->setAlignment(Qt::AlignmentFlag::AlignCenter);

    QFont font = label->font();
    font.setPixelSize(11);
    label->setFont(font);

    QPalette palette = label->palette();
    palette.setColor(QPalette::ColorRole::WindowText, Colors::neutral5());
    label->setPalette(palette);

    layout->addWidget(iconBtn, 0, Qt::AlignmentFlag::AlignCenter);
    layout->addWidget(label, 0, Qt::AlignmentFlag::AlignCenter);
}

// ==================== ModuleCenterPage ====================

ModuleCenterPage::ModuleCenterPage(QWidget* parent)
    : BasePage(parent)
{
    setTargetSize(QSize(300, 300));

    QBoxLayout* mainLayout = setMainLayout('v');

    // 模块网格（按注册页面的 moduleName 动态生成）
    auto* gridWidget = new QWidget(this);
    m_gridLayout = new QGridLayout(gridWidget);
    m_gridLayout->setContentsMargins(4, 4, 4, 4);
    m_gridLayout->setHorizontalSpacing(12);
    m_gridLayout->setVerticalSpacing(12);

    mainLayout->addWidget(gridWidget);
    mainLayout->addStretch();
}

void ModuleCenterPage::onShow()
{
    // 进入页面时：幂等连接各页面的名称变化信号，并按最新名称全量刷新
    connectNameSignals();
    refresh();
}

void ModuleCenterPage::connectNameSignals()
{
    if (m_signalsConnected)
        return;
    m_signalsConnected = true;
    const QList<IPage*> pages = PageRouter::instance().pageList;
    for (IPage* page : pages) {
        const QString name = page->pageName();
        page->addModuleNameChangedCallback(
            [this, name]() { onModuleNameChanged(name); });
    }
}

void ModuleCenterPage::refresh()
{
    // 清空旧卡片
    while (m_gridLayout->count()) {
        QLayoutItem* item = m_gridLayout->takeAt(0);
        if (QWidget* w = item->widget())
            w->deleteLater();
        delete item;
    }
    m_cards.clear();

    // index 按注册顺序对所有页面计数（含空名页面），保持与 Python enumerate 一致的网格位置
    const QList<IPage*> pages = PageRouter::instance().pageList;
    for (int index = 0; index < pages.size(); ++index) {
        IPage* page = pages.at(index);
        if (page->moduleName().isEmpty())
            continue;

        auto* card = new ModuleCard(QString(), QString(), this);
        // 点击行为由页面自身决定（IPage::onModuleCenterClicked），本页不感知任何模块特殊性
        connect(card->iconBtn, &SvgButton::clicked,
                card->iconBtn, [page]() { page->onModuleCenterClicked(); });
        const int row = index / GRID_COLS;
        const int col = index % GRID_COLS;
        m_gridLayout->addWidget(card, row, col);
        m_cards.insert(page->pageName(), card);
        applyModuleCenterInfo(card, page);
    }
}

void ModuleCenterPage::onModuleNameChanged(const QString& pageName)
{
    IPage* page = PageRouter::instance().pages.value(pageName, nullptr);
    if (!page)
        return;
    ModuleCard* card = m_cards.value(pageName, nullptr);
    if (!card) {
        // 变化来自尚未展示的页面（如首次出现）：整体重建一次
        refresh();
        return;
    }
    applyModuleCenterInfo(card, page);
}

void ModuleCenterPage::applyModuleCenterInfo(ModuleCard* card, IPage* page)
{
    card->label->setText(page->moduleName());
    const QString icon = page->moduleIcon();
    if (!icon.isEmpty())
        card->iconBtn->setSvg(icon);
}
