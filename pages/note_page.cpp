#include "pages/note_page.h"

#include "resources/colors.h"
#include "resources/constants.h"
#include "widgets/core_button.h"
#include "widgets/text_editor.h"

#include <QBoxLayout>
#include <QCursor>
#include <QDir>
#include <QFile>
#include <QFont>
#include <QHideEvent>
#include <QLabel>
#include <QPalette>
#include <QTextCursor>

NotePage::NotePage(QWidget* parent)
    : BasePage(parent)
{
    setTargetSize(QSize(400, 300));

    // 便笺数据文件：开发目录放在 exe 目录，打包环境放在 %APPDATA%（与配置文件同目录）
    m_noteFile = dataFilePath(QStringLiteral("notes.txt"));

    // 防抖保存定时器：textChanged 触发重启计时，超时后写盘
    m_saveTimer.setSingleShot(true);
    m_saveTimer.setInterval(SAVE_DEBOUNCE_MS);
    connect(&m_saveTimer, &QTimer::timeout, this, &NotePage::saveNote);

    QBoxLayout* layout = setMainLayout('v');

    // 便笺编辑区（圆角深色背景，与翻译页输入框同款）
    m_noteEditor = new RoundedTextEdit(QStringLiteral("Write something here..."),
                                       Colors::neutral1(), 12, this);
    QFont font;
    font.setPointSize(12);
    m_noteEditor->setFont(font);
    connect(m_noteEditor, &RoundedTextEdit::textChanged, this, &NotePage::onTextChanged);

    // 底部状态栏：保存状态 + 字数统计 + 清空按钮
    m_statusLabel = makeFooterLabel();
    m_charCountLabel = makeFooterLabel();

    m_clearBtn = new CoreButton(QStringLiteral("Clear"), QColor(), QColor(), 12, this);
    m_clearBtn->setBgColor(Colors::danger());
    m_clearBtn->setCursor(Qt::PointingHandCursor);
    connect(m_clearBtn, &CoreButton::clicked, this, &NotePage::clearNote);

    auto* footerLayout = new QHBoxLayout();
    footerLayout->addWidget(m_statusLabel);
    footerLayout->addStretch();
    footerLayout->addWidget(m_charCountLabel);
    footerLayout->addWidget(m_clearBtn);

    layout->addWidget(m_noteEditor);
    layout->addLayout(footerLayout);

    loadNote();
}

QLabel* NotePage::makeFooterLabel()
{
    // 底部状态栏的灰色小字标签
    auto* label = new QLabel(this);
    QFont labelFont = label->font();
    labelFont.setPixelSize(11);
    label->setFont(labelFont);

    QPalette palette = label->palette();
    palette.setColor(QPalette::ColorRole::WindowText, Colors::neutral4());
    label->setPalette(palette);
    return label;
}

// ==================== 数据读写 ====================

void NotePage::loadNote()
{
    // 启动时从磁盘载入便笺内容
    QString content;
    QFile file(m_noteFile);
    if (file.open(QIODevice::ReadOnly | QIODevice::Text))
        content = QString::fromUtf8(file.readAll());

    m_loading = true;
    m_noteEditor->setPlainText(content);
    m_loading = false;
    refreshCharCount();
}

void NotePage::saveNote()
{
    // 把编辑区内容写入磁盘，并刷新保存状态
    QDir().mkpath(QFileInfo(m_noteFile).absolutePath());
    QFile file(m_noteFile);
    if (file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        file.write(m_noteEditor->toPlainText().toUtf8());
        file.close();
        m_statusLabel->setText(QStringLiteral("Saved"));
    } else {
        m_statusLabel->setText(QStringLiteral("Save failed"));
        qWarning("[NotePage] 便笺保存失败");
    }
}

void NotePage::flushSave()
{
    // 立即落盘：防抖计时器还在跑时直接写盘，避免退出时丢失最后一次输入
    if (m_saveTimer.isActive()) {
        m_saveTimer.stop();
        saveNote();
    }
}

// ==================== 交互逻辑 ====================

void NotePage::onTextChanged()
{
    if (m_loading)
        return;
    m_statusLabel->setText(QStringLiteral("Saving..."));
    refreshCharCount();
    m_saveTimer.start();   // 重启计时实现防抖
}

void NotePage::refreshCharCount()
{
    m_charCountLabel->setText(QStringLiteral("%1 chars").arg(m_noteEditor->toPlainText().size()));
}

void NotePage::clearNote()
{
    m_noteEditor->clear();   // 触发 textChanged，自动进入防抖保存流程
    m_noteEditor->setFocus();
}

// ==================== 页面生命周期 ====================

void NotePage::onShow()
{
    // 显示便笺时聚焦编辑区，光标移到末尾方便续写
    QTextCursor cursor = m_noteEditor->textCursor();
    cursor.movePosition(QTextCursor::MoveOperation::End);
    m_noteEditor->setTextCursor(cursor);
    m_noteEditor->setFocus();
}

void NotePage::clearData()
{
    // 便笺内容需要跨会话保留：退出页面只做立即落盘，不清空编辑区
    flushSave();
}

void NotePage::hideEvent(QHideEvent* event)
{
    // 页面被切走（含应用退出收尾）时立即落盘
    flushSave();
    BasePage::hideEvent(event);
}
