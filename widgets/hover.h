#pragma once

// 通用精准悬停组件基类（对应 widgets/hover.py）
// 完全绕过原生的 enterEvent/leaveEvent，采用纯数学几何距离判定。

#include <QEvent>
#include <QObject>
#include <QPointF>
#include <QWidget>

class QPainterPath;

class HoverShape
{
public:
    enum Kind {
        Rectangle,    // 矩形
        Circle,       // 内切圆/正圆
        RoundedRect,  // 圆角矩形
        Custom,       // 自定义路径
    };
};

class HoverWidget : public QWidget
{
    Q_OBJECT

public:
    explicit HoverWidget(QWidget* parent = nullptr,
                         HoverShape::Kind shape = HoverShape::Rectangle,
                         double borderRadius = 0.0);

    // 动态设置检测形状
    void setHoverShape(HoverShape::Kind shape, double borderRadius = 0.0);

    // 如果 shape 选择 Custom，子类可重写此函数返回任意矢量形状
    virtual QPainterPath getCustomPath() const;

    // 根据当前设定的几何形状，精准检测点 pos 是否在内部
    bool containsPoint(const QPointF& pos) const;

    bool event(QEvent* event) override;

signals:
    void hoverEntered();       // 鼠标真正进入几何区域
    void hoverLeft();          // 鼠标真正离开几何区域
    void clicked(bool checked = false);  // 在几何区域内完成有效点击

protected:
    // 虚函数：供子类覆盖（也可以直接连接 hoverEntered / hoverLeft 信号）
    virtual void onHoverEnter() {}
    virtual void onHoverLeave() {}

    void mousePressEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    void updateHoverState(bool isHovered);

    HoverShape::Kind m_shape;
    double m_borderRadius;
    bool m_isHovered = false;
    bool m_isPressed = false;
};
