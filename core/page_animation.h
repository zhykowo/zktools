#pragma once

// 页面切换动画管理器（对应 core/page_animation.py）
// QObject 以支持信号：页面暗下瞬间通知路由层执行 on_show

#include <QObject>
#include <QRect>
#include <QString>

#include <functional>

class QWidget;
class QStackedWidget;
class QGraphicsOpacityEffect;
class QPropertyAnimation;
class QParallelAnimationGroup;
class QSequentialAnimationGroup;
class IPage;

class PageAnimationManager : public QObject
{
    Q_OBJECT

public:
    PageAnimationManager(QWidget* containerWidget, QStackedWidget* stackedWidget,
                         QGraphicsOpacityEffect* opacityEffect,
                         int maxWidth = 450, int maxHeight = 400,
                         QObject* parent = nullptr);

    // 圆角更新回调（容器随尺寸变化调整圆角）
    std::function<void(int)> onRadiusUpdate;

    // 仅改变容器尺寸到指定宽高（不切换页面，不影响透明度）
    void animateSizeTo(int targetW, int targetH);

    // 组合动画：尺寸变化 + 透明度切换（透明度暗下瞬间发 pageSwitched 信号）
    void switchTo(IPage* targetPage, const QString& pageName);

signals:
    // 透明度完全暗下、已切到目标页索引时发出，携带页面名
    void pageSwitched(const QString& pageName);

private:
    QPropertyAnimation* createSizeAnimation(const QRect& startGeom, const QRect& endGeom);
    QSequentialAnimationGroup* createOpacitySwitchAnimation(int targetIndex,
                                                            const QString& pageName);

    // 透明度完全暗下的瞬间：切换堆叠索引，并通知路由层执行目标页 onShow
    void applyPageSwitch(int targetIndex, const QString& pageName);
    void onSizeChanged(const QRect& currentRect);
    void clearAnimation();

    QWidget* m_container;
    QStackedWidget* m_stackedWidget;
    QGraphicsOpacityEffect* m_opacityEffect;
    int m_maxWidth;
    int m_maxHeight;
    QParallelAnimationGroup* m_masterTimeline = nullptr;
};
