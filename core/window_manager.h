#pragma once

// 窗口悬浮岛管理器（对应 core/window_manager.py）：显示/隐藏/拖拽/复位动画

#include <QPoint>
#include <QWidget>

#include <QObject>

class QPropertyAnimation;
class WindowDragFilter;

// 拖拽请求信号总线（对应 Python 的 drag_bus 模块级单例）
class DragBus : public QObject
{
    Q_OBJECT

public:
    static DragBus& instance();

signals:
    // 发送需要绑定拖拽的 QWidget 实例
    void registerDragHandleRequested(QWidget* widget);

private:
    explicit DragBus() = default;
};

class WindowManager
{
public:
    explicit WindowManager(QWidget* window);

    bool isExpanded = false;
    bool onFocus = false;
    bool queueState = false;

    // 注册任意组件/按钮为拖拽手柄
    void registerDragHandle(QWidget* widget);

    // 执行显示/隐藏或复位动画
    // recenter=true 时强制 X 轴水平归位到中央锚点，否则保持当前 X 轴位置
    void animate(bool show, bool recenter = false);

    // 处理窗口焦点变化
    void handleFocusChange(bool isActive);

private:
    QWidget* m_window;
    QPropertyAnimation* m_anim;
    WindowDragFilter* m_dragFilter;

    int m_visibleHeight = 320;   // 隐藏时露出的高度（锚点位置）
    int m_islandWidth = 0;
    int m_islandHeight = 0;
    int m_yHidden = 0;
    int m_yShown = -30;
    int m_xCenter = 0;
};

// 拖拽事件过滤器：可安装到任何 Widget 或 Button 上实现拖拽窗口
class WindowDragFilter : public QObject
{
    Q_OBJECT

public:
    explicit WindowDragFilter(QWidget* window);

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    QWidget* m_window;
    QPoint m_dragPos;
};
