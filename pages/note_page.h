#pragma once

// 便笺页（对应 pages/note_page.py）：随手记录的备忘 sticky note。
// 内容自动保存到本地文件（防抖写盘），重启应用后不丢失；
// 退出页面不清空内容（便笺的生命周期跨越页面切换与应用重启）。

#include <QString>
#include <QTimer>

#include "pages/base_page.h"
#include "resources/svgs.h"

class QLabel;
class CoreButton;
class RoundedTextEdit;

class NotePage : public BasePage
{
    Q_OBJECT

public:
    explicit NotePage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("note"); }
    QString title() const override { return QStringLiteral("Notes"); }
    QString moduleName() const override { return QStringLiteral("Notes"); }
    QString moduleIcon() const override { return Svgs::noteIcon(); }

    void onShow() override;
    void clearData() override;

protected:
    void hideEvent(QHideEvent* event) override;

private:
    // 自动保存防抖间隔（毫秒）：停止输入一段时间后才写盘
    static constexpr int SAVE_DEBOUNCE_MS = 500;

    QLabel* makeFooterLabel();

    // ==================== 数据读写 ====================
    void loadNote();
    void saveNote();
    void flushSave();   // 立即落盘：防抖计时器还在跑时直接写盘

    // ==================== 交互逻辑 ====================
    void onTextChanged();
    void refreshCharCount();
    void clearNote();

    QString m_noteFile;   // 便笺数据文件路径
    RoundedTextEdit* m_noteEditor = nullptr;
    QLabel* m_statusLabel = nullptr;
    QLabel* m_charCountLabel = nullptr;
    CoreButton* m_clearBtn = nullptr;
    QTimer m_saveTimer;   // 防抖保存定时器
    bool m_loading = false;   // 载入阶段标志：初始化填充不当作"用户编辑"
};
