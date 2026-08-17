#include "pages/translator_page.h"

#include "core/hotkey_manager.h"
#include "core/page_router.h"
#include "resources/colors.h"
#include "resources/constants.h"
#include "resources/svgs.h"
#include "utils/text_manager.h"
#include "widgets/core_button.h"
#include "widgets/svg_button.h"
#include "widgets/text_editor.h"

#include <QCursor>
#include <QEasingCurve>
#include <QFont>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QParallelAnimationGroup>
#include <QPoint>
#include <QPropertyAnimation>
#include <QVariant>
#include <QWidget>
#include <QtGlobal>

#include <cmath>

// ==================== GridAnimator ====================

GridAnimator::GridAnimator(QObject* parent)
    : QObject(parent)
{
}

void GridAnimator::animateHeights(const QVector<std::tuple<QWidget*, int, int>>& animationsData,
                                  int duration, std::function<void()> onFinished)
{
    // 替换旧动画组：stop 后 deleteLater 释放 C++ 对象，
    // 否则旧组因 parent 指向常驻页面而永不回收，每次交互累积泄漏
    if (m_activeGroup) {
        m_activeGroup->stop();
        m_activeGroup->deleteLater();
        m_activeGroup = nullptr;
    }

    m_activeGroup = new QParallelAnimationGroup(this);

    for (const auto& [widget, startH, endH] : animationsData) {
        widget->setFixedHeight(startH);

        auto* anim = new QPropertyAnimation(widget, QByteArrayLiteral("maximumHeight"),
                                            m_activeGroup);
        anim->setDuration(duration);
        anim->setStartValue(startH);
        anim->setEndValue(endH);
        anim->setEasingCurve(QEasingCurve::OutQuart);

        // 同步更新 minimumHeight
        connect(anim, &QPropertyAnimation::valueChanged, widget,
                [widget](const QVariant& value) { widget->setMinimumHeight(value.toInt()); });

        // 动画结束后的边界对齐处理
        connect(anim, &QPropertyAnimation::finished, widget, [widget, endH]() {
            widget->setMinimumHeight(endH);
            widget->setMaximumHeight(endH);
        });
        m_activeGroup->addAnimation(anim);
    }

    if (onFinished)
        connect(m_activeGroup, &QParallelAnimationGroup::finished, this, onFinished);

    m_activeGroup->start();
}

// ==================== TranslationHotkey ====================

TranslationHotkey::TranslationHotkey(std::function<void()> callback, QString hotkey,
                                     QObject* parent)
    : QObject(parent)
    , m_callback(std::move(callback))
    , m_hotkey(std::move(hotkey))
{
    if (m_hotkey.isEmpty()) {
        m_hotkey = AppConfig::instance().string(QStringLiteral("translator.hotkey"),
                                                QStringLiteral("ctrl+shift+t"));
    }
}

void TranslationHotkey::start()
{
    // 注册全局热键（幂等）
    HotkeyManager& hotkeys = HotkeyManager::instance();
    hotkeys.start();
    if (hotkeys.registerHotkey(m_hotkey, [this]() {
            // HotkeyManager 回调已在 Qt 主线程分发，直接执行一键翻译流程
            if (m_callback)
                m_callback();
        })) {
        m_registered = true;
        qInfo("[TranslationHotkey] 一键翻译已启用，快捷键: %ls",
              reinterpret_cast<const wchar_t*>(m_hotkey.utf16()));
    } else {
        qWarning("[TranslationHotkey] 一键翻译快捷键 %ls 注册失败！",
                 reinterpret_cast<const wchar_t*>(m_hotkey.utf16()));
    }
}

void TranslationHotkey::stop()
{
    if (m_registered) {
        HotkeyManager::instance().unregisterHotkey(m_hotkey);
        m_registered = false;
    }
}

// ==================== TranslationWorker ====================

TranslationWorker::TranslationWorker(Translator* translator, const QString& text,
                                     const QString& server, const QString& fromLang,
                                     const QString& toLang, QObject* parent)
    : QThread(parent)
    , m_translator(translator)
    , m_text(text)
    , m_server(server)
    , m_fromLang(fromLang)
    , m_toLang(toLang)
{
}

void TranslationWorker::run()
{
    if (m_cancelled.loadRelaxed())
        return;
    const QString result = m_translator->translateText(m_text, m_fromLang, m_toLang, m_server);
    if (!m_cancelled.loadRelaxed())
        emit translationDone(result);
}

// ==================== TranslatorPage ====================

const QStringList& TranslatorPage::supportedLanguages()
{
    static const QStringList langs = {
        QStringLiteral("Auto"),    QStringLiteral("English"), QStringLiteral("Chinese"),
        QStringLiteral("Japanese"), QStringLiteral("Korean"),  QStringLiteral("French"),
        QStringLiteral("German"),  QStringLiteral("Spanish"), QStringLiteral("Russian"),
    };
    return langs;
}

const QStringList& TranslatorPage::supportedServers()
{
    static const QStringList servers = {
        QStringLiteral("Google"), QStringLiteral("DeepL"), QStringLiteral("Baidu"),
        QStringLiteral("Bing"),   QStringLiteral("AI1"),   QStringLiteral("AI2"),
    };
    return servers;
}

TranslatorPage::TranslatorPage(QWidget* parent)
    : BasePage(parent)
{
    m_translator = new Translator();
    m_animator = new GridAnimator(this);
    setTargetSize(QSize(400, 300));

    QBoxLayout* layout = setMainLayout('v');

    // 配色：激活态使用 accent 高亮，非激活态使用灰色（参考 text_editor 的暗灰配色）
    m_accentQColor = Colors::getPurestColor(Colors::getAccentColor());
    m_idleBtnBg = Colors::neutral2();

    // 文本输入框与结果框（圆角背景 + accent/灰色状态边框 + placeholder）
    m_inputText = new RoundedTextEdit(QStringLiteral("Enter or paste text here..."),
                                      Colors::neutral1(), 12, this);
    m_resultText = new RoundedTextEdit(QStringLiteral("Translation result"),
                                       Colors::neutral1(), 10, this);

    QFont font;
    font.setPointSize(12);
    m_inputText->setFont(font);
    m_resultText->setFont(font);

    m_resultText->setMinimumHeight(0);
    m_resultText->setMaximumHeight(0);

    // 通用平铺网格选择面板
    m_selectionGridWidget = new QWidget(this);
    m_gridLayout = new QGridLayout(m_selectionGridWidget);
    m_gridLayout->setContentsMargins(0, 0, 0, 10);
    m_gridLayout->setSpacing(GRID_SPACING);

    m_selectionGridWidget->setMinimumHeight(0);
    m_selectionGridWidget->setMaximumHeight(0);

    // 底部控制栏
    auto* footerLayout = new QHBoxLayout();

    footerLayout->addStretch();

    const QString defaultFrom = AppConfig::instance().string(
        QStringLiteral("translator.default_from_lang"), QStringLiteral("Auto"));
    const QString defaultTo = AppConfig::instance().string(
        QStringLiteral("translator.default_to_lang"), QStringLiteral("Chinese"));

    m_originLang = new CoreButton(defaultFrom);
    connect(m_originLang, &CoreButton::clicked, this,
            [this]() { displayLangList(QStringLiteral("origin")); });
    footerLayout->addWidget(m_originLang, 0, Qt::AlignmentFlag::AlignCenter);

    m_swapBtn = new SvgButton(this, 36, 24, Svgs::arrowRightIcon());
    connect(m_swapBtn, &SvgButton::clicked, this, &TranslatorPage::swapLanguages);
    footerLayout->addWidget(m_swapBtn);

    m_targetLang = new CoreButton(defaultTo);
    connect(m_targetLang, &CoreButton::clicked, this,
            [this]() { displayLangList(QStringLiteral("target")); });
    footerLayout->addWidget(m_targetLang, 0, Qt::AlignmentFlag::AlignCenter);

    footerLayout->addStretch();

    // 默认服务：config 指定内部标识符，按钮文本显示 config 中配置的名称
    const QString defaultServer = AppConfig::instance().string(
        QStringLiteral("translator.default_server"), QStringLiteral("Baidu"));
    m_currentServer = supportedServers().contains(defaultServer) ? defaultServer
                                                                 : supportedServers().first();

    m_translationServerBtn = new CoreButton(serverDisplayName(m_currentServer), QColor(),
                                            QColor(), 12, this);
    connect(m_translationServerBtn, &CoreButton::clicked, this,
            &TranslatorPage::startTranslation);
    m_translationServerBtn->setContextMenuPolicy(Qt::ContextMenuPolicy::CustomContextMenu);
    connect(m_translationServerBtn, &QWidget::customContextMenuRequested, this,
            [this](const QPoint&) { displayServerList(); });
    footerLayout->addWidget(m_translationServerBtn);

    // 取消按钮：与翻译按钮共存于布局，翻译时通过 hide/show 切换显示
    m_cancelBtn = new CoreButton(QStringLiteral("Cancel"), QColor(214, 69, 65), QColor(), 12,
                                 this);
    m_cancelBtn->hide();
    connect(m_cancelBtn, &CoreButton::clicked, this, &TranslatorPage::cancelTranslation);
    footerLayout->addWidget(m_cancelBtn);

    footerLayout->addStretch();

    // 布局组织
    layout->addWidget(m_inputText);
    layout->addWidget(m_resultText);
    layout->addLayout(footerLayout);
    layout->addWidget(m_selectionGridWidget);
    layout->addStretch();

    // 初始状态：网格未展开，from/to 语言按钮均置为灰色（否则默认 accent 高亮）
    setLangButtonsActive(GridMode::None);

    // 一键翻译：注册全局热键（复制选中文本 -> 填入输入框 -> 默认服务翻译）
    m_oneClickHotkey = new TranslationHotkey(
        [this]() { onOneClickTranslate(); }, QString(), this);
    m_oneClickHotkey->start();
}

void TranslatorPage::onShow()
{
    TextManager& tm = TextManager::instance();
    const double nowTime = tm.nowSec();
    const double elapsed = nowTime - tm.selectionTime;
    if (elapsed <= 10 && m_inputText->toPlainText().isEmpty()) {
        if (!tm.selectedText.isEmpty()) {
            m_inputText->setText(tm.selectedText);
        } else if (nowTime - tm.copyTime <= 10) {
            m_inputText->setText(tm.clipboardText);
        }
    }
}

void TranslatorPage::onOneClickTranslate()
{
    // 一键翻译：复制选中文本 -> 填入输入框 -> 使用默认服务翻译
    TextManager& tm = TextManager::instance();
    const QString selected = tm.copySelectedText();
    if (selected.isEmpty()) {
        qInfo("[TranslatorPage] 未获取到选中的文本，一键翻译已取消");
        return;
    }

    // 1. 切换到翻译页并展示选中文本
    PageRouter::instance().immediateSwitch(QStringLiteral("translator"));
    m_inputText->setText(selected);
    m_inputText->setFocus();

    m_originLang->setText(AppConfig::instance().string(
        QStringLiteral("translator.default_from_lang"), QStringLiteral("Auto")));
    m_targetLang->setText(AppConfig::instance().string(
        QStringLiteral("translator.default_to_lang"), QStringLiteral("Chinese")));

    // 2. 使用默认服务与默认语言执行翻译
    const QString defaultServer = AppConfig::instance().string(
        QStringLiteral("translator.default_server"), QStringLiteral("Baidu"));
    m_currentServer = supportedServers().contains(defaultServer)
                          ? defaultServer
                          : supportedServers().first();
    m_translationServerBtn->setText(serverDisplayName(m_currentServer));
    startTranslation();
}

// ==================== 抽象核心逻辑 ====================

void TranslatorPage::requestGridSwitch(GridMode mode, const QStringList& items,
                                       const QString& currentValue,
                                       const std::function<void(const QString&)>& onSelectCallback)
{
    // 网格切换控制中心：实现平滑过渡
    if (m_currentGridMode == mode) {
        collapseGrid();
        return;
    }

    const int currentHeight = prepareGridSwitch(mode, items, currentValue, onSelectCallback);
    animateGridSwitch(currentHeight, calculateGridHeight(items.size()));
}

int TranslatorPage::prepareGridSwitch(GridMode mode, const QStringList& items,
                                      const QString& currentValue,
                                      const std::function<void(const QString&)>& onSelectCallback)
{
    // 切换准备：更新网格状态、填充新按钮并固定当前高度防止跳变
    const int currentHeight = m_currentGridMode != GridMode::None
                                  ? m_selectionGridWidget->height()
                                  : 0;
    m_currentGridMode = mode;

    // 填充新按钮并强制固定当前高度防止跳变
    populateGrid(items, currentValue, onSelectCallback);
    setLangButtonsActive(mode);
    m_selectionGridWidget->setMaximumHeight(currentHeight);

    return currentHeight;
}

void TranslatorPage::animateGridSwitch(int currentHeight, int targetHeight)
{
    // 网格展开动画：网格平滑展开，同时收起结果框（若有内容）
    QVector<std::tuple<QWidget*, int, int>> animations;
    animations.append(std::make_tuple(m_selectionGridWidget, currentHeight, targetHeight));
    if (m_resultText->height() > 0)
        animations.append(std::make_tuple(m_resultText, m_resultText->height(), 0));

    m_animator->animateHeights(animations);
}

void TranslatorPage::collapseGrid(std::function<void()> onFinished)
{
    // 收起当前网格动画
    m_currentGridMode = GridMode::None;
    setLangButtonsActive(GridMode::None);
    const int currentHeight = m_selectionGridWidget->height();

    m_animator->animateHeights({std::make_tuple(m_selectionGridWidget, currentHeight, 0)}, 300,
                               std::move(onFinished));
}

void TranslatorPage::populateGrid(const QStringList& items, const QString& currentValue,
                                  const std::function<void(const QString&)>& onSelectCallback)
{
    // 清空旧按钮
    while (m_gridLayout->count()) {
        QLayoutItem* item = m_gridLayout->takeAt(0);
        if (QWidget* w = item->widget())
            w->deleteLater();
        delete item;
    }

    // 创建新按钮
    constexpr int cols = 3;
    for (int idx = 0; idx < items.size(); ++idx) {
        const QString& text = items.at(idx);
        auto* btn = new CoreButton(text);
        btn->setCursor(Qt::PointingHandCursor);
        // 仅当前选中项（激活）以 accent 高亮，其余显示灰色
        if (text != currentValue)
            btn->setBgColor(m_idleBtnBg);

        connect(btn, &CoreButton::clicked, btn, [this, text, onSelectCallback]() {
            handleGridItemClick(text, onSelectCallback);
        });

        const int row = idx / cols;
        const int col = idx % cols;
        m_gridLayout->addWidget(btn, row, col);
    }
}

int TranslatorPage::calculateGridHeight(int itemCount)
{
    constexpr int cols = 3;
    const int rows = (itemCount + cols - 1) / cols;
    return rows * GRID_ITEM_HEIGHT + (rows - 1) * GRID_SPACING;
}

void TranslatorPage::handleGridItemClick(const QString& selectedText,
                                         const std::function<void(const QString&)>& callback)
{
    // 点击网格项后的逻辑处理
    callback(selectedText);
    collapseGrid();
}

void TranslatorPage::displayLangList(const QString& targetType)
{
    // 显示语言选择网格
    const bool origin = targetType == QLatin1String("origin");
    const GridMode mode = origin ? GridMode::OriginLang : GridMode::TargetLang;
    const QString currentLang = origin ? m_originLang->text() : m_targetLang->text();

    auto setLanguage = [this, origin](const QString& selectedLang) {
        if (origin)
            m_originLang->setText(selectedLang);
        else
            m_targetLang->setText(selectedLang);
    };

    requestGridSwitch(mode, supportedLanguages(), currentLang, setLanguage);
}

QString TranslatorPage::serverDisplayName(const QString& serverId)
{
    // 服务按钮显示名：AI1/AI2 使用 config 中指定的名称，其余显示自身标识符
    if (serverId == QLatin1String("AI1") || serverId == QLatin1String("AI2")) {
        const QString name = AppConfig::instance().string(
            QStringLiteral("translator.apis.ai.") + serverId + QStringLiteral(".name"));
        return name.isEmpty() ? serverId : name;
    }
    return serverId;
}

void TranslatorPage::displayServerList()
{
    // 显示翻译服务选择网格（AI1/AI2 显示 config 指定的名称，其余显示自身名称）
    QStringList items;
    m_serverDisplayToId.clear();
    for (const QString& serverId : supportedServers()) {
        const QString displayName = serverDisplayName(serverId);
        m_serverDisplayToId.insert(displayName, serverId);
        items.append(displayName);
    }

    const QString currentDisplay = serverDisplayName(m_currentServer);

    auto setServer = [this](const QString& selectedDisplay) {
        m_currentServer = m_serverDisplayToId.value(selectedDisplay);
        m_translationServerBtn->setText(selectedDisplay);
    };

    requestGridSwitch(GridMode::Server, items, currentDisplay, setServer);
}

// ==================== 翻译流程 ====================

void TranslatorPage::startTranslation()
{
    // 后台线程执行翻译，避免阻塞 UI；翻译期间按钮替换为红色 Cancel 按钮
    if (m_worker)
        return;   // 已有翻译进行中（此时按钮已变为 Cancel，点击即取消）

    const QString text = m_inputText->toPlainText();
    const QString server = m_currentServer;
    const QString fromLang = m_originLang->text();
    const QString toLang = m_targetLang->text();

    qInfo("正在使用 [%ls] 将 '%ls' 从 %ls 翻译为 %ls...",
          reinterpret_cast<const wchar_t*>(server.utf16()),
          reinterpret_cast<const wchar_t*>(text.utf16()),
          reinterpret_cast<const wchar_t*>(fromLang.utf16()),
          reinterpret_cast<const wchar_t*>(toLang.utf16()));

    m_translationCancelled = false;
    setTranslating(true);

    m_worker = new TranslationWorker(m_translator, text, server, fromLang, toLang, this);
    connect(m_worker, &TranslationWorker::translationDone,
            this, &TranslatorPage::onTranslationDone);
    connect(m_worker, &QThread::finished, this, &TranslatorPage::onWorkerFinished);
    m_worker->start();
}

void TranslatorPage::setTranslating(bool translating)
{
    // 隐藏的组件会自动空出布局位置并触发重排，两个按钮在布局中
    // 始终占据同一槽位，因此无需移除/插入即可完成切换
    m_translationServerBtn->setVisible(!translating);
    m_cancelBtn->setVisible(translating);
}

void TranslatorPage::cancelTranslation()
{
    // 取消进行中的翻译：丢弃结果并立即恢复翻译按钮（同步请求无法中断网络传输）
    m_translationCancelled = true;
    TranslationWorker* worker = m_worker;
    m_worker = nullptr;
    if (worker) {
        worker->cancel();
        // 线程结束后自动释放，避免 QThread 对象泄漏
        connect(worker, &QThread::finished, worker, &QObject::deleteLater);
    }
    setTranslating(false);
}

void TranslatorPage::onTranslationDone(const QString& result)
{
    // 翻译完成（主线程）：显示结果并展开结果框
    if (m_translationCancelled) {
        m_translationCancelled = false;
        return;
    }

    m_resultText->setText(result);

    m_currentGridMode = GridMode::None;
    setLangButtonsActive(GridMode::None);

    const int gridStartH = m_selectionGridWidget->height();
    const int resultStartH = m_resultText->height();

    m_animator->animateHeights({
        std::make_tuple(m_selectionGridWidget, gridStartH, 0),
        std::make_tuple(m_resultText, resultStartH, RESULT_TEXT_HEIGHT),
    });
    setTranslating(false);
}

void TranslatorPage::onWorkerFinished()
{
    // 后台线程自然结束（未被取消）：释放 worker
    TranslationWorker* worker = m_worker;
    m_worker = nullptr;
    if (worker)
        worker->deleteLater();
}

void TranslatorPage::setLangButtonsActive(GridMode mode)
{
    // 仅当对应语言网格展开时，from/to 语言按钮才以 accent 高亮，否则显示灰色
    m_originLang->setBgColor(mode == GridMode::OriginLang ? m_accentQColor : m_idleBtnBg);
    m_targetLang->setBgColor(mode == GridMode::TargetLang ? m_accentQColor : m_idleBtnBg);
}

void TranslatorPage::swapLanguages()
{
    // 互换源语言与目标语言
    const QString temp = m_originLang->text();
    m_originLang->setText(m_targetLang->text());
    m_targetLang->setText(temp);
}

void TranslatorPage::onBackClicked()
{
    // 返回逻辑：如果网格开启则收起，否则退出页面
    if (m_currentGridMode != GridMode::None) {
        collapseGrid();
    } else {
        PageRouter::instance().exitSelf(m_pageName);
    }
}

void TranslatorPage::clearData()
{
    cancelTranslation();
    m_inputText->setText(QString());
    m_resultText->setText(QString());

    setLangButtonsActive(GridMode::None);

    m_animator->animateHeights({
        std::make_tuple(m_selectionGridWidget, m_selectionGridWidget->height(), 0),
        std::make_tuple(m_resultText, m_resultText->height(), 0),
    });
}
