#pragma once

// 主页（对应 pages/homepage.py）：两个入口按钮 + 拖放提示

#include <QLabel>
#include <QObject>
#include <QPropertyAnimation>
#include <QString>
#include <QStringList>

#include "pages/base_page.h"

class QDragEnterEvent;
class QDragLeaveEvent;
class QDropEvent;

// 拖拽状态总线（对应 Python 的 on_drag_bus 模块级单例）
class OnDragBus : public QObject
{
    Q_OBJECT

public:
    static OnDragBus& instance();

signals:
    void onDragEvent(bool dragging);

private:
    explicit OnDragBus() = default;
};

class HomePage : public BasePage
{
    Q_OBJECT

public:
    explicit HomePage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("home"); }
    QString title() const override { return QStringLiteral("Home"); }

protected:
    // ---- 拖放（对应 DragDropMixin + HomePage 钩子重写）----
    void dragEnterEvent(QDragEnterEvent* event) override;
    void dragLeaveEvent(QDragLeaveEvent* event) override;
    void dropEvent(QDropEvent* event) override;

    // 子类钩子
    virtual void onDragEnter();
    virtual void onDragLeave();
    virtual void onFilesDropped(const QStringList& filePaths) { Q_UNUSED(filePaths); }
    virtual void onTextDropped(const QString& text) { Q_UNUSED(text); }

private:
    QLabel* m_dropHintLabel = nullptr;
    QPropertyAnimation* m_dropAnim = nullptr;
};
