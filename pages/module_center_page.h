#pragma once

// 模块中心（对应 pages/module_center_page.py）：纯展示页。
//
// 卡片内容不在此硬编码，只读取各页面的 moduleName：
// - 进入页面时（onShow）全量刷新卡片；
// - 页面自身名称变化时（module_name_changed 信号）实时更新对应卡片。
// 点击卡片统一跳转到对应页面，无任何模块特殊逻辑。

#include <QHash>
#include <QString>

#include "pages/base_page.h"

class QGridLayout;
class QLabel;
class SvgButton;

// 单个模块卡片：上图下字组件
class ModuleCard : public QWidget
{
    Q_OBJECT

public:
    explicit ModuleCard(const QString& name = QString(),
                        const QString& iconData = QString(), QWidget* parent = nullptr);

    SvgButton* iconBtn = nullptr;
    QLabel* label = nullptr;
};

class ModuleCenterPage : public BasePage
{
    Q_OBJECT

public:
    explicit ModuleCenterPage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("module_center"); }
    QString title() const override { return QStringLiteral("Module Center"); }

    void onShow() override;

private:
    // 订阅所有已注册页面的名称变化（仅一次）
    void connectNameSignals();
    // 重建卡片网格：只读取各页面的 moduleName/moduleIcon，空名页面不显示
    void refresh();
    // 某页面模块中心信息（名称/图标）变化：实时更新对应卡片
    void onModuleNameChanged(const QString& pageName);
    // 把页面的模块中心名称与图标应用到卡片（构建与信号刷新共用同一逻辑）
    static void applyModuleCenterInfo(ModuleCard* card, IPage* page);

    static constexpr int GRID_COLS = 3;

    QGridLayout* m_gridLayout = nullptr;
    QHash<QString, ModuleCard*> m_cards;   // pageName -> ModuleCard
    bool m_signalsConnected = false;
};
