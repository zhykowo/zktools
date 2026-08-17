#pragma once

// 页面路由（单例，对应 core/page_router.py）：信号入口 + 全局状态 + 切换调度，三合一。
//
//     PageRouter::instance().immediateSwitch("setting");   // 发切换请求
//     PageRouter::instance().exitSelf("short_text");       // 精确退出指定页
//     PageRouter::instance().gentleSwitch("translator");   // 温和排队切换
//
// 约定：pageQueue 的队首（pageQueue[0]）即当前正在显示的页面，
// 队列正常至少保留 "home"（清空后自动补回）。

#include <QHash>
#include <QList>
#include <QObject>
#include <QString>
#include <QStringList>

class IPage;
class PageAnimationManager;
class WindowManager;

class PageRouter : public QObject
{
    Q_OBJECT

public:
    enum class SwitchMode {
        Gentle,      // 温和切换：加入队列排队
        Immediate,   // 立即切换：插队并强制中断当前页面
        ExitSelf,    // 退出自己：当前页面结束，释放并展示队列下一页
    };
    Q_ENUM(SwitchMode)

    static PageRouter& instance();

    // ---------- 全局状态 ----------
    QList<IPage*> pageList;            // 按注册顺序保存（模块中心枚举用，Python dict 保序）
    QHash<QString, IPage*> pages;      // 页面注册池 { "page_name": page }
    QStringList pageQueue;             // 队首即当前显示页；至少保留 "home"

    // 主窗口在初始化完成后注入 UI 协作对象
    void bind(WindowManager* windowManager, PageAnimationManager* animationManager);

    // 注册无界面模块（"假页面"）：只进页面池供模块中心枚举，不加入堆叠窗口
    IPage* registerVirtual(IPage* page);

    // ---------- 信号入口 ----------
    void gentleSwitch(const QString& pageName);     // 温和切换：仅加入队列
    void immediateSwitch(const QString& pageName);  // 立即切换：立刻中断并显示目标页
    void exitSelf(const QString& pageName = QString());

signals:
    // 传递切换模式和目标页面标识（同线程直连，dispatch 同步消费）
    void dispatchRequested(PageRouter::SwitchMode mode, const QString& pageName);

private slots:
    // 核心路由控制阀：按模式调度页面
    void dispatch(SwitchMode mode, const QString& pageName);

private:
    explicit PageRouter();

    // 队首即当前页：弹出旧当前页，新队首成为当前页并渲染；队列清空则回到 home
    void nextPage();

    // 动画透明度暗下、页面索引切换完成时，调用目标页 onShow
    void onPageSwitched(const QString& pageName);

    WindowManager* m_windowManager = nullptr;
    PageAnimationManager* m_animationManager = nullptr;
};
