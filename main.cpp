// zktools C++ 版入口（对应 zktools/main.py）

#include <QApplication>
#include <QEvent>
#include <QFont>
#include <QGraphicsOpacityEffect>
#include <QHBoxLayout>
#include <QPalette>
#include <QPoint>
#include <QRect>
#include <QStackedWidget>
#include <QVariantAnimation>
#include <QWidget>
#include <QtGlobal>

#include "core/page_animation.h"
#include "core/page_router.h"
#include "core/window_manager.h"
#include "pages/base_page.h"
#include "pages/clipboard_ctl_page.h"
#include "pages/homepage.h"
#include "pages/module_center_page.h"
#include "pages/note_page.h"
#include "pages/notify_page.h"
#include "pages/setting_page.h"
#include "pages/touchpad_ctl_page.h"
#include "pages/translator_page.h"
#include "resources/colors.h"
#include "utils/clipboard_monitor.h"
#include "utils/mouse_tracker.h"
#include "utils/text_manager.h"
#include "widgets/main_container.h"

#include <windows.h>

// 主窗口类
class MainShellWindow : public QWidget
{
    Q_OBJECT

public:
    explicit MainShellWindow(QWidget* parent = nullptr);

    // 动态注册页面，方便未来无缝扩展更多页面
    void registerPage(const QString& name, BasePage* page);

protected:
    // 当鼠标进入灵动岛容器时触发闪烁
    bool eventFilter(QObject* watched, QEvent* event) override;
    // 当窗口的激活状态发生改变时触发
    void changeEvent(QEvent* event) override;

private:
    void initUi();
    // 原生更新容器圆角
    void updateContainerRadius(int radius);
    void createAnim();
    // 灵动岛高亮脉冲闪烁动画
    void triggerFlashEffect();

    static constexpr int MAX_W = 450;
    static constexpr int MAX_H = 400;

    // 页面状态与切换逻辑统一托管在 PageRouter 单例中（见 core/page_router.cpp），
    // 子模块可直接读取或发起切换，无需经由此窗口实例。

    WindowManager* m_windowManager = nullptr;
    MainContainerWidget* m_mainContainer = nullptr;
    QStackedWidget* m_stackedWidget = nullptr;
    QGraphicsOpacityEffect* m_opacityEffect = nullptr;
    PageAnimationManager* m_animationManager = nullptr;
    QVariantAnimation* m_flashAnim = nullptr;

    void changeDragState(bool state) { Q_UNUSED(state); }
};

MainShellWindow::MainShellWindow(QWidget* parent)
    : QWidget(parent)
{
    // 绑定拖拽状态总线（主页拖放时广播）
    connect(&OnDragBus::instance(), &OnDragBus::onDragEvent,
            this, [this](bool state) { changeDragState(state); });

    setWindowFlags(Qt::WindowType::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::Tool);
    setAttribute(Qt::WidgetAttribute::WA_TranslucentBackground);

    resize(MAX_W, MAX_H);

    m_windowManager = new WindowManager(this);
    // 监听全局拖拽注册请求
    connect(&DragBus::instance(), &DragBus::registerDragHandleRequested,
            this, [this](QWidget* widget) { m_windowManager->registerDragHandle(widget); });

    initUi();
}

void MainShellWindow::registerPage(const QString& name, BasePage* page)
{
    // 动态注册页面，方便未来无缝扩展更多页面
    PageRouter& router = PageRouter::instance();
    router.pages.insert(name, page);
    router.pageList.append(page);
    page->setPageName(name);
    m_stackedWidget->addWidget(page);
}

void MainShellWindow::initUi()
{
    PageRouter& router = PageRouter::instance();

    QPalette palette = this->palette();
    palette.setColor(QPalette::ColorRole::WindowText, Colors::white());
    setPalette(palette);

    QFont font;
    font.setPointSize(12);
    setFont(font);

    m_mainContainer = new MainContainerWidget(this);
    m_mainContainer->setObjectName(QStringLiteral("MainContainer"));
    m_mainContainer->installEventFilter(this);

    auto* containerLayout = new QHBoxLayout(m_mainContainer);
    containerLayout->setContentsMargins(10, 0, 10, 0);
    containerLayout->setSpacing(5);

    m_stackedWidget = new QStackedWidget(m_mainContainer);

    m_opacityEffect = new QGraphicsOpacityEffect(m_stackedWidget);
    m_stackedWidget->setGraphicsEffect(m_opacityEffect);

    // 注册名统一取自各页面的 pageId() 值（页面三名称之一，见 pages/base_page.h）
    registerPage(QStringLiteral("home"), new HomePage());
    registerPage(QStringLiteral("setting"), new SettingPage());
    registerPage(QStringLiteral("notify"), new NotifyPage());
    // 无界面模块（假页面，见 pages/notify_page.h 的 VirtualPage）：
    // 只进页面池供模块中心枚举，不加入堆叠窗口、不可切换显示
    router.registerVirtual(new ClipboardCtlPage());
    router.registerVirtual(new TouchpadCtlPage());
    registerPage(QStringLiteral("module_center"), new ModuleCenterPage());
    registerPage(QStringLiteral("translator"), new TranslatorPage());
    registerPage(QStringLiteral("note"), new NotePage());

    router.pageQueue = {QStringLiteral("home")};   // 队首即当前页，初始为 home
    m_stackedWidget->setCurrentWidget(
        static_cast<BasePage*>(router.pages.value(QStringLiteral("home"))->asWidget()));

    containerLayout->addWidget(m_stackedWidget);

    const QSize startSize = router.pages.value(QStringLiteral("home"))->targetSize();
    m_mainContainer->setGeometry(
        (MAX_W - startSize.width()) / 2, 40, startSize.width(), startSize.height());

    // 动画管理器设置
    m_animationManager = new PageAnimationManager(m_mainContainer, m_stackedWidget,
                                                  m_opacityEffect, MAX_W, MAX_H, this);

    // 设置圆角更新回调
    m_animationManager->onRadiusUpdate = [this](int radius) { updateContainerRadius(radius); };
    updateContainerRadius(25);
    createAnim();

    // 将窗口/动画管理器注入路由单例，路由请求由 PageRouter 统一调度
    router.bind(m_windowManager, m_animationManager);
}

void MainShellWindow::updateContainerRadius(int radius)
{
    // 原生更新容器圆角
    m_mainContainer->setRadius(radius);
}

bool MainShellWindow::eventFilter(QObject* watched, QEvent* event)
{
    // 当鼠标进入灵动岛容器时触发闪烁
    if (watched == m_mainContainer && event->type() == QEvent::Enter) {
        TextManager::instance().getSelectedText();
        triggerFlashEffect();
    }
    return QWidget::eventFilter(watched, event);
}

void MainShellWindow::createAnim()
{
    // 创建颜色渐变动画
    m_flashAnim = new QVariantAnimation(this);
    m_flashAnim->setDuration(220);   // 闪烁持续时间 (毫秒)
    m_flashAnim->setStartValue(m_mainContainer->defaultBackgroundColor().lighter(255));  // 闪烁高亮颜色
    m_flashAnim->setEndValue(m_mainContainer->defaultBackgroundColor());                 // 恢复基础背景色

    connect(m_flashAnim, &QVariantAnimation::valueChanged, this,
            [this](const QVariant& value) {
                m_mainContainer->setBackgroundColor(value.value<QColor>());
            });
}

void MainShellWindow::triggerFlashEffect()
{
    // 灵动岛高亮脉冲闪烁动画
    const PageRouter& router = PageRouter::instance();
    if (!router.pageQueue.isEmpty() && router.pageQueue.first() != QLatin1String("home"))
        return;
    // 防止动画重复叠加
    if (m_flashAnim && m_flashAnim->state() == QVariantAnimation::Running)
        return;

    m_flashAnim->start();
}

void MainShellWindow::changeEvent(QEvent* event)
{
    // 当窗口的激活状态发生改变时触发
    if (event->type() == QEvent::ActivationChange)
        m_windowManager->handleFocusChange(isActiveWindow());
    QWidget::changeEvent(event);
}

// ==================== 入口 ====================

int main(int argc, char* argv[])
{
    QApplication app(argc, argv);

    // COM（UI Automation 取词、剪贴板 OLE 需要）
    const HRESULT hr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    // 通过 QFont 修正字体渲染
    QFont font = app.font();
    // PreferQuality：匹配字体时，选择最接近的标准点大小
    // PreferAntialias：渲染时，尽可能开启抗锯齿
    font.setStyleStrategy(static_cast<QFont::StyleStrategy>(
        QFont::StyleStrategy::PreferQuality | QFont::StyleStrategy::PreferAntialias));
    font.setHintingPreference(QFont::HintingPreference::PreferNoHinting);
    app.setFont(font);

    ClipboardMonitor::instance();
    TextManager::instance();

    // 安装全局鼠标追踪事件过滤器（debug=false，直通不打印）
    MouseHoverEventFilter mouseTracker(false);
    app.installEventFilter(&mouseTracker);

    // 触摸板状态机预热：启动时读取系统真实状态（与 Python 版模块导入时机一致）
    TouchpadController::instance();

    MainShellWindow window;
    window.show();

    const int code = app.exec();
    if (SUCCEEDED(hr))
        CoUninitialize();
    return code;
}

#include "main.moc"
