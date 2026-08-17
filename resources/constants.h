#pragma once

// 配置与数据文件路径（对应 resources/constants.py）
//
// 配置查找优先级：exe 目录下 config_dev.json -> config.json -> %APPDATA%\zHyko\PYDi\config.json，
// 全部不存在时把默认配置写入 %APPDATA% 后返回默认值。
// 数据文件（便笺等）与配置文件同目录：开发目录（exe 旁有 config*.json）放 exe 目录，
// 否则放 %APPDATA%\zHyko\PYDi\。

#include <QJsonObject>
#include <QString>

class AppConfig
{
public:
    // 首次访问时加载配置（懒加载单例）
    static AppConfig& instance();

    // 以 "translator.hotkey" 这样的点路径读取字符串，缺省返回 def
    QString string(const QString& dotPath, const QString& def = QString()) const;

    // 以点路径读取 JSON 对象，不存在返回空对象
    QJsonObject object(const QString& dotPath) const;

private:
    AppConfig();
    QJsonObject m_root;
};

// exe 所在目录（Python 版的 root_dir = Path(sys.argv[0]).resolve().parent）
QString appRootDir();

// 用户数据文件路径（优先级与配置文件一致，目录不存在时自动创建）
QString dataFilePath(const QString& filename);
