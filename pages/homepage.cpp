#include "pages/homepage.h"

#include "core/page_router.h"
#include "resources/colors.h"
#include "resources/svgs.h"
#include "widgets/svg_button.h"

#include <QDragEnterEvent>
#include <QDragLeaveEvent>
#include <QDropEvent>
#include <QBoxLayout>
#include <QEasingCurve>
#include <QMimeData>
#include <QSizePolicy>
#include <QUrl>

// ==================== OnDragBus ====================

OnDragBus& OnDragBus::instance()
{
    static OnDragBus bus;
    return bus;
}

// ==================== HomePage ====================

namespace {
// 拖拽提示样式（颜色统一由 colors 管理）
QString dropHintIdleQss()
{
    return QStringLiteral("color: %1; font-size: 18px; "
                           "border: 2px dashed %2; border-radius: 5px; ")
        .arg(Colors::toQssColor(Colors::transparent()), Colors::toQssColor(Colors::neutral4()));
}

QString dropHintActiveQss()
{
    return QStringLiteral("color: %1; font-size: 18px; "
                           "border: 2px dashed %2; border-radius: 5px; ")
        .arg(Colors::toQssColor(Colors::white()), Colors::toQssColor(Colors::neutral4()));
}
} // namespace

HomePage::HomePage(QWidget* parent)
    : BasePage(parent)
{
    setAcceptDrops(true);

    setTargetSize(QSize(140, 50));

    QBoxLayout* layout = setMainLayout('h');

    // 设置按钮 (齿轮)
    auto* settingBtn = new SvgButton(nullptr, 36, 22, Svgs::settingsIcon(), QColor(), true);
    connect(settingBtn, &SvgButton::clicked, this,
            []() { PageRouter::instance().immediateSwitch(QStringLiteral("setting")); });

    auto* appCenterBtn = new SvgButton(nullptr, 36, 22, Svgs::appCenterIcon(), QColor(), true);
    connect(appCenterBtn, &SvgButton::clicked, this,
            []() { PageRouter::instance().immediateSwitch(QStringLiteral("module_center")); });

    m_dropHintLabel = new QLabel(QStringLiteral("Drag here"), this);
    m_dropHintLabel->setAlignment(Qt::AlignmentFlag::AlignCenter);
    m_dropHintLabel->setStyleSheet(dropHintIdleQss());
    m_dropHintLabel->setSizePolicy(QSizePolicy::Policy::Expanding, QSizePolicy::Policy::Expanding);
    m_dropHintLabel->setMaximumWidth(0);

    layout->addWidget(settingBtn);
    layout->addWidget(appCenterBtn);
    layout->addWidget(m_dropHintLabel);

    m_dropAnim = new QPropertyAnimation(m_dropHintLabel, QByteArrayLiteral("maximumWidth"), this);
    m_dropAnim->setDuration(800);
    m_dropAnim->setEasingCurve(QEasingCurve::OutQuart);
}

// ---- 拖放事件（对应 DragDropMixin）----

void HomePage::dragEnterEvent(QDragEnterEvent* event)
{
    // 同时允许 带有文件链接(Urls) 或 纯文本(Text) 的内容拖入
    if (event->mimeData()->hasUrls() || event->mimeData()->hasText()) {
        event->acceptProposedAction();
        onDragEnter();
    } else {
        event->ignore();
    }
}

void HomePage::dragLeaveEvent(QDragLeaveEvent* event)
{
    onDragLeave();
    event->accept();
}

void HomePage::dropEvent(QDropEvent* event)
{
    onDragLeave();   // 放下通常也意味着离开拖拽状态

    const QMimeData* mimeData = event->mimeData();
    if (mimeData->hasUrls()) {
        QStringList filePaths;
        const QList<QUrl> urls = mimeData->urls();
        for (const QUrl& url : urls)
            filePaths.append(url.toLocalFile());
        onFilesDropped(filePaths);
        event->acceptProposedAction();
    } else if (mimeData->hasText()) {
        onTextDropped(mimeData->text());
        event->acceptProposedAction();
    }
}

void HomePage::onDragEnter()
{
    m_dropHintLabel->setStyleSheet(dropHintActiveQss());
    emit OnDragBus::instance().onDragEvent(true);
    m_dropAnim->stop();
    m_dropAnim->setEndValue(0);
    m_dropAnim->start();
}

void HomePage::onDragLeave()
{
    emit OnDragBus::instance().onDragEvent(false);
    m_dropAnim->stop();
    m_dropAnim->setEndValue(0);
    m_dropAnim->start();
}
