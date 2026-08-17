#pragma once

// 自绘圆角按钮（对应 widgets/core_button.py）

#include <QColor>
#include <QPushButton>

class QPaintEvent;

class CoreButton : public QPushButton
{
    Q_OBJECT

public:
    explicit CoreButton(const QString& text, const QColor& bgColor = QColor(),
                        const QColor& textColor = QColor(), int radius = 12,
                        QWidget* parent = nullptr);

    void setBgColor(const QColor& bgColor);
    void resetBgColor();

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    QColor m_accentQColor;
    QColor m_bgColor;
    QColor m_textColor;
    int m_radius;
};
