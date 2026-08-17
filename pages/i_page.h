#pragma once

// 页面统一接口（对应 Python 里 BasePage / VirtualPage 的共同协议）
//
// Python 版鸭子类型直接读写 page_name / target_size / module_name 等属性；
// C++ 版真实页面 = QWidget + IPage（BasePage），无界面"假页面" = QObject + IPage
// （VirtualPage），页面池统一持有 IPage*。
//
// 页面三名称约定（与 Python 版一致）：
// - pageName():   代码内注册名（page_router 路由标识，注册时由路由写入）
// - title():      页面标题栏显示文本（仅 BasePage）
// - moduleName(): 模块中心显示名；空字符串表示不显示在模块中心
// - moduleIcon(): 卡片图标（SVG 数据）

#include <QSize>
#include <QString>

#include <functional>

class QObject;
class QWidget;

class IPage
{
public:
    virtual ~IPage() = default;

    // Qt 信号连接用（真实页面与虚拟页面都是 QObject）
    virtual QObject* asQObject() = 0;

    // 可显示页面返回对应 QWidget（虚拟页面返回 nullptr）
    virtual QWidget* asWidget() { return nullptr; }

    virtual QString pageName() const = 0;
    virtual void setPageName(const QString& name) = 0;

    // 类级页面标识（对应 Python 的 PAGE_NAME 类属性）：注册进页面池时使用
    virtual QString pageId() const { return QString(); }

    virtual QSize targetSize() const = 0;
    virtual void setTargetSize(const QSize& size) {}

    virtual void onShow() {}
    virtual void clearData() {}

    virtual QString moduleName() const = 0;
    virtual QString moduleIcon() const = 0;

    // 模块中心卡片点击行为
    virtual void onModuleCenterClicked() {}

    // 路由层标记：无界面，不可切换显示
    virtual bool isVirtual() const = 0;

    // 模块中心名称变化通知（对应 Python 的 module_name_changed 信号）
    virtual void addModuleNameChangedCallback(std::function<void()> callback) = 0;

protected:
    virtual void notifyModuleNameChanged() = 0;
};
