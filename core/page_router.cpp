#include "core/page_router.h"

#include "core/page_animation.h"
#include "core/window_manager.h"
#include "pages/i_page.h"

#include <QtGlobal>

PageRouter& PageRouter::instance()
{
    static PageRouter router;
    return router;
}

PageRouter::PageRouter()
{
    // 单例导入即接管全局路由请求，无需手动连接（同线程直连，同步分发）
    connect(this, &PageRouter::dispatchRequested, this, &PageRouter::dispatch);
}

void PageRouter::bind(WindowManager* windowManager, PageAnimationManager* animationManager)
{
    if (windowManager)
        m_windowManager = windowManager;
    if (animationManager) {
        m_animationManager = animationManager;
        // 透明度完全暗下（页面切换完成）的瞬间才触发目标页 onShow
        connect(m_animationManager, &PageAnimationManager::pageSwitched,
                this, &PageRouter::onPageSwitched);
    }
}

IPage* PageRouter::registerVirtual(IPage* page)
{
    // 只进入页面池供模块中心枚举卡片，不加入堆叠窗口；
    // dispatch 会拒绝把虚拟页面作为切换目标。
    pages[page->pageId()] = page;
    page->setPageName(page->pageId());
    pageList.append(page);
    return page;
}

void PageRouter::onPageSwitched(const QString& pageName)
{
    // 动画透明度暗下、页面索引切换完成时，调用目标页的 onShow
    IPage* page = pages.value(pageName, nullptr);
    if (page)
        page->onShow();
}

// ---------- 信号入口 ----------

void PageRouter::gentleSwitch(const QString& pageName)
{
    emit dispatchRequested(SwitchMode::Gentle, pageName);
}

void PageRouter::immediateSwitch(const QString& pageName)
{
    emit dispatchRequested(SwitchMode::Immediate, pageName);
}

void PageRouter::exitSelf(const QString& pageName)
{
    // 带 pageName：精确退出该页面；不带：保持旧语义，退出当前正在显示的页面
    emit dispatchRequested(SwitchMode::ExitSelf, pageName);
}

// ---------- 调度逻辑 ----------

void PageRouter::dispatch(SwitchMode mode, const QString& pageName)
{
    if (!m_windowManager || !m_animationManager) {
        qInfo("[page_router] 尚未 bind 窗口管理器/动画管理器，忽略路由请求: %d %ls",
              int(mode), reinterpret_cast<const wchar_t*>(pageName.utf16()));
        return;
    }

    // 温和/立即切换的目标必须是可显示的实体页面：
    // 未注册或虚拟页面（无界面模块）直接忽略
    if (mode != SwitchMode::ExitSelf) {
        IPage* page = pages.value(pageName, nullptr);
        if (!page || page->isVirtual()) {
            qInfo("[page_router] 忽略对不可显示页面的切换请求: %ls",
                  reinterpret_cast<const wchar_t*>(pageName.utf16()));
            return;
        }
    }

    m_windowManager->queueState = true;
    m_windowManager->animate(true);

    if (mode == SwitchMode::Gentle) {
        // 1. 温和切换：仅塞入队列（已在队列中则跳过，保证队列有界、不重复排队）
        const bool wasIdle = pageQueue.isEmpty();
        if (!pageQueue.contains(pageName))
            pageQueue.append(pageName);
        // 若当前页为 home（处于空闲）则直接触发下一页
        if (wasIdle || pageQueue.first() == QLatin1String("home"))
            nextPage();

    } else if (mode == SwitchMode::Immediate) {
        // 2. 立即切换：插队逻辑
        if (pageQueue.isEmpty() || pageQueue.first() != pageName) {
            // 目标页成为新的当前页（队首）；原当前页留在队列中等待其退出后无缝恢复。
            // 去重：若目标页已在队列中排队，先移除旧位置，避免高频触发下队列无限增长。
            pageQueue.removeAll(pageName);
            pageQueue.prepend(pageName);
        }
        // onShow 由动画透明度暗下瞬间的 pageSwitched 信号触发
        m_animationManager->switchTo(pages.value(pageName), pageName);

    } else if (mode == SwitchMode::ExitSelf) {
        // 精确退出：pageName 指定要退出的页面，而不是盲目退当前页
        if (!pageName.isEmpty()) {
            if (!pageQueue.isEmpty() && pageQueue.first() == pageName) {
                // 目标页面正在显示（队首）：清数据并调度下一页
                IPage* current = pages.value(pageName, nullptr);
                if (current)
                    current->clearData();
                nextPage();
            } else if (pageQueue.contains(pageName)) {
                // 目标页面被插队顶到队列中：直接从队列移除，无需切换
                pageQueue.removeAll(pageName);
            }
            // 否则：目标页面既不在当前也不在队列，什么都不做
        }
    }
}

void PageRouter::nextPage()
{
    // 弹出旧当前页（队首），新队首自动成为当前页
    if (!pageQueue.isEmpty())
        pageQueue.removeFirst();
    if (pageQueue.isEmpty()) {
        // 队列清空（退出最后一页/异常兜底）：补回 home
        pageQueue.append(QStringLiteral("home"));
    }
    const QString nextName = pageQueue.first();
    // onShow 由动画透明度暗下瞬间的 pageSwitched 信号触发
    m_animationManager->switchTo(pages.value(nextName), nextName);
    if (nextName == QLatin1String("home")) {
        // 显示/回到 home：归位居中显示
        m_windowManager->queueState = false;
        m_windowManager->animate(m_windowManager->onFocus, true);
    }
}
