#pragma once

// 圆角文本编辑框（对应 widgets/text_editor.py）：圆角背景 + 状态边框 + placeholder
//
// QTextEdit 的可视区域是 viewport，背景/边框/placeholder 全部绘制在 viewport 上，
// 且 Base 色必须保持透明，否则基类 paintEvent 会覆盖背景。

#include <QColor>
#include <QTextEdit>

class QPaintEvent;

class RoundedTextEdit : public QTextEdit
{
    Q_OBJECT

public:
    explicit RoundedTextEdit(const QString& placeholder = QString(),
                             const QColor& bgColor = QColor(), int radius = 12,
                             QWidget* parent = nullptr);

    void setPlaceholder(const QString& text);
    QString getPlaceholder() const { return m_placeholder; }

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    QString m_placeholder;
    int m_radius;
    QColor m_bgColor;
    QColor m_accent;
    QColor m_idleBorder;
    QColor m_hoverBorder;
    QColor m_placeholderColor;
};
