#include "pages/setting_page.h"

#include <QBoxLayout>
#include <QLabel>

SettingPage::SettingPage(QWidget* parent)
    : BasePage(parent)
{
    setTargetSize(QSize(300, 300));

    QBoxLayout* layout = setMainLayout('v');

    auto* titleLabel = new QLabel(QStringLiteral("⚙️ 这是设置页面"), this);
    titleLabel->setAlignment(Qt::AlignmentFlag::AlignCenter);

    layout->addStretch();
    layout->addWidget(titleLabel);
    layout->addStretch();
}
