#pragma once

// 翻译页（对应 pages/translator_page.py）

#include <QColor>
#include <QHash>
#include <QAtomicInt>
#include <QObject>
#include <QPointer>
#include <QString>
#include <QThread>
#include <QVector>

#include <functional>
#include <tuple>

#include "pages/base_page.h"
#include "resources/svgs.h"
#include "utils/translator.h"

class QGridLayout;
class QParallelAnimationGroup;
class QWidget;
class CoreButton;
class RoundedTextEdit;
class SvgButton;

// 语言/服务选择网格的展开状态
enum class GridMode
{
    None,
    OriginLang,
    TargetLang,
    Server,
};

// 动画管理器，支持平滑高度动画与链式回调
class GridAnimator : public QObject
{
    Q_OBJECT

public:
    explicit GridAnimator(QObject* parent = nullptr);

    // 对 (widget, startH, endH) 列表执行平行高度动画
    void animateHeights(const QVector<std::tuple<QWidget*, int, int>>& animationsData,
                        int duration = 300,
                        std::function<void()> onFinished = nullptr);

private:
    QPointer<QParallelAnimationGroup> m_activeGroup;
};

// 一键翻译全局热键：按下快捷键后自动完成
// 复制选中文本 -> 填入输入框 -> 使用默认服务翻译
// （HotkeyManager 的回调已在 Qt 主线程分发，可直接执行）
class TranslationHotkey : public QObject
{
    Q_OBJECT

public:
    explicit TranslationHotkey(std::function<void()> callback, QString hotkey = QString(),
                               QObject* parent = nullptr);

    QString hotkey() const { return m_hotkey; }

    // 注册全局热键（幂等）
    void start();
    // 注销全局热键
    void stop();

private:
    std::function<void()> m_callback;
    QString m_hotkey;
    bool m_registered = false;
};

// 后台翻译线程：translateText 是同步阻塞调用（含网络请求），
// 放入 QThread 执行，完成后通过信号把结果回传主线程；
// 调用 cancel() 后结果将被丢弃，不再更新界面。
class TranslationWorker : public QThread
{
    Q_OBJECT

public:
    TranslationWorker(Translator* translator, const QString& text, const QString& server,
                      const QString& fromLang, const QString& toLang, QObject* parent = nullptr);

    // 请求取消：置标志，翻译结果将被丢弃（同步请求无法中断网络传输）
    void cancel() { m_cancelled.storeRelaxed(1); }

    void run() override;

signals:
    void translationDone(const QString& result);

private:
    Translator* m_translator;
    QString m_text;
    QString m_server;
    QString m_fromLang;
    QString m_toLang;
    QAtomicInt m_cancelled{0};
};

class TranslatorPage : public BasePage
{
    Q_OBJECT

public:
    explicit TranslatorPage(QWidget* parent = nullptr);

    QString pageId() const override { return QStringLiteral("translator"); }
    QString title() const override { return QStringLiteral("Translator"); }
    QString moduleName() const override { return QStringLiteral("Translator"); }
    QString moduleIcon() const override { return Svgs::translateIcon(); }

    void onShow() override;
    void onBackClicked() override;
    void clearData() override;

private:
    // ==================== 抽象核心逻辑 ====================
    // 网格切换控制中心：实现平滑过渡
    void requestGridSwitch(GridMode mode, const QStringList& items, const QString& currentValue,
                           const std::function<void(const QString&)>& onSelectCallback);
    // 切换准备：更新网格状态、填充新按钮并固定当前高度防止跳变，返回切换前高度
    int prepareGridSwitch(GridMode mode, const QStringList& items, const QString& currentValue,
                          const std::function<void(const QString&)>& onSelectCallback);
    // 网格展开动画：网格平滑展开，同时收起结果框（若有内容）
    void animateGridSwitch(int currentHeight, int targetHeight);
    // 收起当前网格动画
    void collapseGrid(std::function<void()> onFinished = nullptr);
    void populateGrid(const QStringList& items, const QString& currentValue,
                      const std::function<void(const QString&)>& onSelectCallback);
    int calculateGridHeight(int itemCount);
    // 点击网格项后的逻辑处理
    void handleGridItemClick(const QString& selectedText,
                             const std::function<void(const QString&)>& callback);

    // ==================== 语言/服务选择 ====================
    void displayLangList(const QString& targetType = QStringLiteral("origin"));
    // 服务按钮显示名：AI1/AI2 使用 config 中指定的名称，其余显示自身标识符
    QString serverDisplayName(const QString& serverId);
    void displayServerList();

    // ==================== 翻译流程 ====================
    void startTranslation();
    // 翻译中显示红色 Cancel 按钮、隐藏翻译按钮；结束时反向
    void setTranslating(bool translating);
    void cancelTranslation();
    void onTranslationDone(const QString& result);
    void onWorkerFinished();
    void setLangButtonsActive(GridMode mode);
    void swapLanguages();
    // 一键翻译：复制选中文本 -> 填入输入框 -> 使用默认服务翻译
    void onOneClickTranslate();

    Translator* m_translator = nullptr;
    GridAnimator* m_animator = nullptr;

    // 后台翻译线程状态
    QPointer<TranslationWorker> m_worker;
    bool m_translationCancelled = false;

    // 当前展开的网格类型状态
    GridMode m_currentGridMode = GridMode::None;

    // 配色：激活态使用 accent 高亮，非激活态使用灰色
    QColor m_accentQColor;
    QColor m_idleBtnBg;

    // 输入框与结果框
    RoundedTextEdit* m_inputText = nullptr;
    RoundedTextEdit* m_resultText = nullptr;

    // 通用平铺网格选择面板
    QWidget* m_selectionGridWidget = nullptr;
    QGridLayout* m_gridLayout = nullptr;

    // 底部控制栏
    CoreButton* m_originLang = nullptr;
    SvgButton* m_swapBtn = nullptr;
    CoreButton* m_targetLang = nullptr;
    CoreButton* m_translationServerBtn = nullptr;
    CoreButton* m_cancelBtn = nullptr;

    QString m_currentServer;
    QHash<QString, QString> m_serverDisplayToId;   // 显示名 -> 服务标识符

    TranslationHotkey* m_oneClickHotkey = nullptr;

    static const QStringList& supportedLanguages();
    static const QStringList& supportedServers();

    static constexpr int GRID_ITEM_HEIGHT = 36;
    static constexpr int GRID_SPACING = 8;
    static constexpr int RESULT_TEXT_HEIGHT = 120;
};
