#include "utils/switch_touchpad.h"

#include "resources/constants.h"

#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QtGlobal>

#include <windows.h>

namespace SwitchTouchpad {

namespace {

// 运行 PowerShell 脚本并返回 UTF-8 标准输出；失败返回空
// （脚本开头强制 [Console]::OutputEncoding = UTF8，保证中文设备名解码稳定）
QString runPowerShell(const QString& script)
{
    QProcess process;
    const QString fullScript =
        QStringLiteral("[Console]::OutputEncoding=[Text.Encoding]::UTF8; ") + script;
    process.start(QStringLiteral("pwsh.exe"),
                  { QStringLiteral("-NoProfile"), QStringLiteral("-Command"), fullScript });

    if (!process.waitForStarted(5000)) {
        qWarning("[switch_touchpad] 无法启动 pwsh.exe");
        return QString();
    }
    if (!process.waitForFinished(30000)) {
        qWarning("[switch_touchpad] pwsh 执行超时");
        process.kill();
        process.waitForFinished(3000);
        return QString();
    }
    if (process.exitStatus() != QProcess::NormalExit || process.exitCode() != 0) {
        const QString err = QString::fromUtf8(process.readAllStandardError());
        qWarning("[switch_touchpad] PowerShell 脚本执行失败: %ls",
                 reinterpret_cast<const wchar_t*>(err.trimmed().utf16()));
        return QString();
    }
    return QString::fromUtf8(process.readAllStandardOutput());
}

// 解析 ConvertTo-Json 输出；单个设备时是对象而非数组，统一包成数组
QJsonArray parseDeviceArray(const QString& jsonText)
{
    if (jsonText.trimmed().isEmpty()) {
        qInfo("[switch_touchpad] 未找到匹配的触摸板设备。");
        return {};
    }
    const QJsonDocument doc = QJsonDocument::fromJson(jsonText.toUtf8());
    if (!doc.isObject() && !doc.isArray()) {
        qWarning("[switch_touchpad] JSON 解析失败");
        return {};
    }
    if (doc.isObject())
        return QJsonArray{doc.object()};
    return doc.array();
}

QList<DeviceInfo> queryDevices(bool withStatus)
{
    const QString fields = withStatus
        ? QStringLiteral("FriendlyName, InstanceId, Status, ConfigManagerErrorCode")
        : QStringLiteral("FriendlyName, InstanceId");
    const QString script = QStringLiteral(
        "Get-PnpDevice | Where-Object { "
        "$_.FriendlyName -match \"Touchpad|Touch Pad|触摸板\" } | "
        "Select-Object %1 | ConvertTo-Json").arg(fields);

    const QJsonArray devices = parseDeviceArray(runPowerShell(script));
    QList<DeviceInfo> result;
    for (const QJsonValue& v : devices) {
        if (!v.isObject())
            continue;
        const QJsonObject obj = v.toObject();
        DeviceInfo info;
        info.friendlyName = obj.value(QStringLiteral("FriendlyName")).toString();
        info.instanceId = obj.value(QStringLiteral("InstanceId")).toString();
        info.configManagerErrorCode =
            obj.value(QStringLiteral("ConfigManagerErrorCode")).toInt(-1);
        result.append(info);
    }
    return result;
}

} // namespace

QList<DeviceInfo> getTouchpadDevices()
{
    return queryDevices(false);
}

std::optional<bool> getTouchpadStatus()
{
    const QList<DeviceInfo> devices = queryDevices(true);
    if (devices.isEmpty())
        return std::nullopt;

    // 只要还有任一设备处于启用状态，就认为触摸板整体可用
    for (const DeviceInfo& device : devices) {
        if (device.configManagerErrorCode == 0)
            return true;
    }
    return false;
}

bool runPsAsAdmin(const QString& scriptPath, const QString& arguments)
{
    const QString nativePath = QDir::toNativeSeparators(scriptPath);
    const QString psArgs = QStringLiteral(
        "-NoProfile -ExecutionPolicy Bypass -File \"%1\" %2").arg(nativePath, arguments);

    qInfo("[+] 正在尝试以管理员权限启动 PowerShell 脚本: %ls",
          reinterpret_cast<const wchar_t*>(nativePath.utf16()));

    // ShellExecuteW "runas" 触发 UAC 提权
    const HINSTANCE result = ShellExecuteW(
        nullptr, L"runas", L"pwsh.exe",
        reinterpret_cast<LPCWSTR>(psArgs.utf16()),
        nullptr, SW_SHOWNORMAL);

    const INT_PTR retval = reinterpret_cast<INT_PTR>(result);
    if (retval > 32) {
        qInfo("[+] 提权请求已发送，请在 UAC 弹窗中点击\"是\"。");
        return true;
    }
    qWarning("[-] 启动失败，错误码: %lld", static_cast<qint64>(retval));
    return false;
}

void runSwitchTouchpad(bool enable)
{
    const QString scriptPath =
        QDir(appRootDir()).filePath(QStringLiteral("tools/Set-PnpDeviceState.ps1"));
    const QString actionValue = enable ? QStringLiteral("Enable")
                                       : QStringLiteral("Disable");

    const QList<DeviceInfo> touchpadList = getTouchpadDevices();
    qInfo("找到 %lld 个相关设备：", static_cast<qint64>(touchpadList.size()));

    for (const DeviceInfo& device : touchpadList) {
        if (device.instanceId.isEmpty())
            continue;

        qInfo("设备名称: %ls\n实例 ID : %ls\n----------------------------------------",
              reinterpret_cast<const wchar_t*>(device.friendlyName.utf16()),
              reinterpret_cast<const wchar_t*>(device.instanceId.utf16()));

        const QString psArguments = QStringLiteral(R"(-Action "%1" -InstanceId "%2")")
                                        .arg(actionValue, device.instanceId);
        runPsAsAdmin(scriptPath, psArguments);
    }
}

} // namespace SwitchTouchpad
