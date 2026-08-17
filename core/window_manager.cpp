#include "core/window_manager.h"

#include <QEvent>
#include <QGuiApplication>
#include <QMouseEvent>
#include <QPoint>
#include <QPropertyAnimation>
#include <QScreen>
#include <QEasingCurve>
#include <QtGlobal>

// ==================== WindowDragFilter ====================

WindowDragFilter::WindowDragFilter(QWidget* window)
    : QObject(window)
    , m_window(window)
{
}

bool WindowDragFilter::eventFilter(QObject* watched, QEvent* event)
{
    if (event->type() == QEvent::MouseButtonPress) {
        auto* mouse = static_cast<QMouseEvent*>(event);
        if (mouse->button() == Qt::LeftButton) {
            // 记录点击时鼠标相对窗口左上角的偏移量
            m_dragPos = mouse->globalPosition().toPoint() - m_window->pos();
            return true;
        }
    } else if (event->type() == QEvent::MouseMove) {
        auto* mouse = static_cast<QMouseEvent*>(event);
        if (mouse->buttons() & Qt::LeftButton) {
            // 随鼠标移动更新窗口位置
            m_window->move(mouse->globalPosition().toPoint() - m_dragPos);
            return true;
        }
    }
    return QObject::eventFilter(watched, event);
}

// ==================== DragBus ====================

DragBus& DragBus::instance()
{
    static DragBus bus;
    return bus;
}

// ==================== WindowManager ====================

WindowManager::WindowManager(QWidget* window)
    : m_window(window)
{
    // 计算位置参数（锚点位置）
    const QRect screen = QGuiApplication::primaryScreen()->geometry();
    m_islandWidth = window->width();
    m_islandHeight = window->height();

    m_yHidden = -m_islandHeight + m_visibleHeight;
    m_yShown = -30;
    m_xCenter = (screen.width() - m_islandWidth) / 2;

    // 拖拽过滤器实例
    m_dragFilter = new WindowDragFilter(window);

    // 初始化位置（默认隐藏）
    window->move(m_xCenter, m_yHidden);

    // 创建动画
    m_anim = new QPropertyAnimation(window, QByteArrayLiteral("pos"), window);
    m_anim->setDuration(800);
    m_anim->setEasingCurve(QEasingCurve::OutBack);
}

void WindowManager::registerDragHandle(QWidget* widget)
{
    widget->installEventFilter(m_dragFilter);
}

void WindowManager::animate(bool show, bool recenter)
{
    // 若非强制归位，且展开状态无变化，或触发了阻止隐藏的保护条件，则跳过
    if (!recenter) {
        if (isExpanded == show)
            return;
        if (isExpanded && !show && (queueState || onFocus))
            return;
    }

    isExpanded = show;

    // 确定目标坐标
    const int targetX = recenter ? m_xCenter : m_window->x();
    const int targetY = show ? m_yShown : m_yHidden;

    m_anim->stop();
    m_anim->setEndValue(QPoint(targetX, targetY));
    m_anim->start();
}

void WindowManager::handleFocusChange(bool isActive)
{
    onFocus = isActive;
    animate(isActive);
}
