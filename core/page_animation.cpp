#include "core/page_animation.h"

#include "pages/i_page.h"

#include <QEasingCurve>
#include <QGraphicsOpacityEffect>
#include <QParallelAnimationGroup>
#include <QPropertyAnimation>
#include <QSequentialAnimationGroup>
#include <QStackedWidget>
#include <QWidget>

PageAnimationManager::PageAnimationManager(QWidget* containerWidget,
                                           QStackedWidget* stackedWidget,
                                           QGraphicsOpacityEffect* opacityEffect,
                                           int maxWidth, int maxHeight, QObject* parent)
    : QObject(parent)
    , m_container(containerWidget)
    , m_stackedWidget(stackedWidget)
    , m_opacityEffect(opacityEffect)
    , m_maxWidth(maxWidth)
    , m_maxHeight(maxHeight)
{
}

// ---------- 基础动画创建 ----------

QPropertyAnimation* PageAnimationManager::createSizeAnimation(const QRect& startGeom,
                                                              const QRect& endGeom)
{
    // 返回一个几何动画对象（未启动）
    auto* anim = new QPropertyAnimation(m_container, QByteArrayLiteral("geometry"));
    anim->setDuration(500);
    anim->setEasingCurve(QEasingCurve::OutBack);
    anim->setStartValue(startGeom);
    anim->setEndValue(endGeom);
    return anim;
}

QSequentialAnimationGroup* PageAnimationManager::createOpacitySwitchAnimation(int targetIndex,
                                                                              const QString& pageName)
{
    // 透明度切换串行动画组（淡出→切换索引→淡入）
    const qreal currentOpacity = m_opacityEffect->opacity();

    auto* fadeOut = new QPropertyAnimation(m_opacityEffect, QByteArrayLiteral("opacity"));
    fadeOut->setDuration(int(400 * currentOpacity));
    fadeOut->setEasingCurve(QEasingCurve::OutCubic);
    fadeOut->setStartValue(currentOpacity);
    fadeOut->setEndValue(0.0);
    connect(fadeOut, &QPropertyAnimation::finished, this,
            [this, targetIndex, pageName]() { applyPageSwitch(targetIndex, pageName); });

    auto* fadeIn = new QPropertyAnimation(m_opacityEffect, QByteArrayLiteral("opacity"));
    fadeIn->setDuration(200);
    fadeIn->setStartValue(0.0);
    fadeIn->setEndValue(1.0);

    auto* seq = new QSequentialAnimationGroup(m_container);
    seq->addAnimation(fadeOut);
    seq->addAnimation(fadeIn);
    return seq;
}

// ---------- 公共接口 ----------

void PageAnimationManager::animateSizeTo(int targetW, int targetH)
{
    // 仅改变容器尺寸到指定宽高（不切换页面，不影响透明度）
    clearAnimation();
    const QRect currentGeom = m_container->geometry();
    const int endX = (m_maxWidth - targetW) / 2;
    const int endY = 40;
    const QRect endGeom(endX, endY, targetW, targetH);
    if (currentGeom == endGeom)
        return;

    QPropertyAnimation* sizeAnim = createSizeAnimation(currentGeom, endGeom);
    // 尺寸变化时更新圆角
    if (onRadiusUpdate) {
        connect(sizeAnim, &QPropertyAnimation::valueChanged, this,
                [this](const QVariant& value) { onSizeChanged(value.toRect()); });
    }

    m_masterTimeline = new QParallelAnimationGroup(m_container);
    m_masterTimeline->addAnimation(sizeAnim);
    connect(m_masterTimeline, &QParallelAnimationGroup::finished,
            this, &PageAnimationManager::clearAnimation);
    m_masterTimeline->start();
}

void PageAnimationManager::switchTo(IPage* targetPage, const QString& pageName)
{
    // 组合动画：尺寸变化 + 透明度切换（透明度暗下瞬间发 pageSwitched 信号）
    clearAnimation();
    const int index = m_stackedWidget->indexOf(targetPage->asWidget());
    const QSize targetSize = targetPage->targetSize();
    const int targetW = targetSize.width();
    const int targetH = targetSize.height();
    const int endX = (m_maxWidth - targetW) / 2;
    const int endY = 40;
    const QRect endGeom(endX, endY, targetW, targetH);
    const QRect currentGeom = m_container->geometry();

    QPropertyAnimation* sizeAnim = createSizeAnimation(currentGeom, endGeom);
    if (onRadiusUpdate) {
        connect(sizeAnim, &QPropertyAnimation::valueChanged, this,
                [this](const QVariant& value) { onSizeChanged(value.toRect()); });
    }

    QSequentialAnimationGroup* opacitySwitch = createOpacitySwitchAnimation(index, pageName);

    // 并行执行尺寸动画和透明度切换
    auto* parallel = new QParallelAnimationGroup(m_container);
    parallel->addAnimation(sizeAnim);
    parallel->addAnimation(opacitySwitch);

    m_masterTimeline = parallel;
    connect(m_masterTimeline, &QParallelAnimationGroup::finished,
            this, &PageAnimationManager::clearAnimation);
    m_masterTimeline->start();
}

// ---------- 内部辅助 ----------

void PageAnimationManager::applyPageSwitch(int targetIndex, const QString& pageName)
{
    // 透明度完全暗下的瞬间：切换堆叠索引，并通知路由层执行目标页 onShow
    m_stackedWidget->setCurrentIndex(targetIndex);
    emit pageSwitched(pageName);
}

void PageAnimationManager::onSizeChanged(const QRect& currentRect)
{
    if (onRadiusUpdate)
        onRadiusUpdate(qMin(25, currentRect.height() / 2 - 1));
}

void PageAnimationManager::clearAnimation()
{
    if (m_masterTimeline) {
        m_masterTimeline->stop();
        m_masterTimeline->deleteLater();
        m_masterTimeline = nullptr;
    }
}
