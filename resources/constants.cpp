#include "resources/constants.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QStandardPaths>
#include <QtGlobal>

namespace {

// 与开发目录下 config.json 内容一致的默认配置模板
QByteArray defaultConfigJson()
{
    return QByteArrayLiteral(R"({
    "touchpad_ctl": {
        "hotkeys": {
            "switch": "ctrl+shift+b",
            "test": "ctrl+alt+a"
        }
    },
    "translator": {
        "hotkey": "ctrl+shift+s",
        "default_server": "Baidu",
        "default_from_lang": "Auto",
        "default_to_lang": "Chinese",
        "apis": {
            "baidu": {
                "appid": "your_appid",
                "secret_key": "your_secret_key"
            },
            "deepl": {
                "api_key": "your_deepl_api_key"
            },
            "google": {
                "api_key": "your_google_api_key"
            },
            "bing": {
                "api_key": "your_bing_api_key",
                "region": ""
            },
            "ai": {
                "AI1": {
                    "name": "AI1",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "your_api_key",
                    "model": "gpt-4o-mini"
                },
                "AI2": {
                    "name": "AI2",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "your_api_key",
                    "model": "deepseek-chat"
                }
            }
        }
    }
})");
}

// %APPDATA%（Python 版回退到 ~/.config，这里统一用 QStandardPaths 等价实现）
QString appdataDir()
{
    const QString appdata = qEnvironmentVariable("APPDATA");
    if (!appdata.isEmpty())
        return appdata;
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
}

QJsonDocument loadConfigDocument()
{
    const QDir root(appRootDir());
    const QStringList candidates = {
        root.filePath(QStringLiteral("config_dev.json")),
        root.filePath(QStringLiteral("config.json")),
        QDir(appdataDir()).filePath(QStringLiteral("zHyko/PYDi/config.json")),
    };

    for (const QString& path : candidates) {
        QFile file(path);
        if (!file.exists() || !file.open(QIODevice::ReadOnly))
            continue;
        QJsonParseError err{};
        const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
        file.close();
        if (err.error == QJsonParseError::NoError && doc.isObject())
            return doc;
        qWarning("[constants] 配置文件解析失败: %ls (%ls)",
                 reinterpret_cast<const wchar_t*>(path.utf16()),
                 reinterpret_cast<const wchar_t*>(err.errorString().utf16()));
    }

    // 全部不存在：创建 %APPDATA%\zHyko\PYDi\ 并写入默认配置
    const QString appdataConfig = candidates.last();
    QDir().mkpath(QFileInfo(appdataConfig).absolutePath());
    QFile out(appdataConfig);
    if (out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        QJsonDocument doc = QJsonDocument::fromJson(defaultConfigJson());
        out.write(doc.toJson(QJsonDocument::Indented));
        out.close();
    }
    return QJsonDocument::fromJson(defaultConfigJson());
}

} // namespace

AppConfig& AppConfig::instance()
{
    static AppConfig cfg;
    return cfg;
}

AppConfig::AppConfig()
{
    const QJsonDocument doc = loadConfigDocument();
    m_root = doc.object();
}

QString AppConfig::string(const QString& dotPath, const QString& def) const
{
    QJsonObject node = m_root;
    const QStringList parts = dotPath.split(QLatin1Char('.'));
    for (int i = 0; i < parts.size() - 1; ++i) {
        const QJsonValue v = node.value(parts[i]);
        if (!v.isObject())
            return def;
        node = v.toObject();
    }
    if (parts.isEmpty())
        return def;
    const QJsonValue v = node.value(parts.last());
    return v.isString() ? v.toString() : def;
}

QJsonObject AppConfig::object(const QString& dotPath) const
{
    QJsonObject node = m_root;
    const QStringList parts = dotPath.split(QLatin1Char('.'));
    for (const QString& part : parts) {
        const QJsonValue v = node.value(part);
        if (!v.isObject())
            return {};
        node = v.toObject();
    }
    return node;
}

QString appRootDir()
{
    return QCoreApplication::applicationDirPath();
}

QString dataFilePath(const QString& filename)
{
    const QDir root(appRootDir());
    if (QFile::exists(root.filePath(QStringLiteral("config_dev.json")))
        || QFile::exists(root.filePath(QStringLiteral("config.json")))) {
        return root.filePath(filename);
    }

    QDir dataDir(QDir(appdataDir()).filePath(QStringLiteral("zHyko/PYDi")));
    dataDir.mkpath(QStringLiteral("."));
    return dataDir.filePath(filename);
}
