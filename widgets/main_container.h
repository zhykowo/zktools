#pragma once

// 自定义主容器（对应 widgets/main_container.py）：QPainter 原生绘制圆角背景 + 渐变描边

#include <QColor>
#include <QWidget>

class QPaintEvent;

class MainContainerWidget : public QWidget
{
    Q_OBJECT

public:
    explicit MainContainerWidget(QWidget* parent = nullptr);

    QColor defaultBackgroundColor() const { return m_defaultBackgroundColor; }

    // 动态更新背景颜色并触发重绘
    void setBackgroundColor(const QColor& color);

    // 动态更新圆角半径并触发重绘
    void setRadius(int radius);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    QColor m_defaultBackgroundColor;
    QColor m_backgroundColor;
    QColor m_borderColorStart;   // 渐变起点（左上，最亮）
    QColor m_borderColorEnd;     // 渐变终点（右下，偏灰）
    int m_borderWidth = 1;
    int m_currentRadius = 25;
};
