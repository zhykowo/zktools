#pragma once

// SVG 图标按钮（对应 widgets/svg_button.py）
// 继承 HoverWidget，天然具备圆形碰撞判定与物理 Hover 检测；
// 光栅化缓存：SVG 只渲染一次，hover 动画每帧仅做位图染色。

#include <QColor>
#include <QPixmap>
#include <QPropertyAnimation>
#include <QWidget>

#include "widgets/hover.h"

class QSvgRenderer;
class QPaintEvent;

class SvgButton : public HoverWidget
{
    Q_OBJECT
    // hover 进度属性动画（0.0 -> 1.0），驱动背景透明度/图标染色/旋转
    Q_PROPERTY(float hoverProgress READ hoverProgress WRITE setHoverProgress)

public:
    explicit SvgButton(QWidget* parent = nullptr, int size = 36, int iconSize = 16,
                       const QString& svgData = QString(),
                       const QColor& hoverColor = QColor(),
                       bool enableRotation = false);

    // 加载 SVG（svgData 以 ".svg" 结尾时按文件路径加载，否则按 SVG 文本加载）
    void setSvg(const QString& svgData);

    float hoverProgress() const { return m_hoverProgress; }
    void setHoverProgress(float value);

protected:
    // 重写基类的进入/离开钩子函数
    void onHoverEnter() override;
    void onHoverLeave() override;

    void paintEvent(QPaintEvent* event) override;

private:
    // 惰性构建 SVG 光栅化缓存；仅当 SVG / iconSize / dpr 变化时重建
    void ensureIconCache();
    // 把缓存图标染成 (normal -> target) 的插值色；复用成员 pixmap，避免每帧分配
    QPixmap buildTintedPixmap(float p);

    int m_iconSize;
    QColor m_normalColor;
    QColor m_targetColor;
    bool m_enableRotation;

    QSvgRenderer* m_svgRenderer;
    QPixmap m_iconCache;     // 原始 SVG 渲染结果
    QPixmap m_tintPixmap;    // 每帧复用的染色目标
    double m_cachedDpr = 0.0;
    int m_cachedIconSize = 0;

    float m_hoverProgress = 0.0f;
    QPropertyAnimation* m_animation;
};
