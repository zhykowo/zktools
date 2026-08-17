#pragma once

// 翻译服务实现（对应 utils/translator.py）
//
// Python 版基于 httpx（同步阻塞），C++ 版用 QNetworkAccessManager + 本地 QEventLoop
// 实现同步语义；本类在工作线程（TranslationWorker）中调用，线程内自建 QNAM。
//
// 支持服务：
// - Google: 免费网页接口（无需 key）；配置 api_key 后优先走付费官方 API
// - DeepL: 官方 API，付费 key 走 api.deepl.com；未配置 / :fx 免费 key 走免费端点
// - Baidu: 官方 API，需 config 的 translator.apis.baidu.appid / secret_key
// - Bing: 配置有效 key 时优先走 Azure 付费官方 API，否则走微软 Edge 免费接口
// - AI1 / AI2: OpenAI 兼容 Chat API，由 config 的 translator.apis.ai.<AI1|AI2> 指定

#include <QByteArray>
#include <QHash>
#include <QJsonObject>
#include <QList>
#include <QMap>
#include <QString>
#include <QUrl>

class Translator
{
public:
    Translator();

    // 按服务标识符分发翻译；统一捕获异常，保证 UI 不崩溃
    QString translateText(const QString& text,
                          const QString& fromLang = QStringLiteral("Auto"),
                          const QString& toLang = QStringLiteral("Chinese"),
                          const QString& server = QStringLiteral("Baidu"));

private:
    struct HttpReply
    {
        int status = 0;
        QByteArray body;
        QString error;   // 非空表示网络层失败（超时 / 连接错误）
        bool ok() const { return error.isEmpty(); }
    };

    // 同步 HTTP 基础设施（在调用线程内自建 QNAM + 本地事件循环）
    static HttpReply httpGet(const QUrl& url, int timeoutMs);
    static HttpReply httpPostForm(const QUrl& url,
                                  const QList<QPair<QString, QString>>& form,
                                  int timeoutMs);
    static HttpReply httpPostJson(const QUrl& url, const QByteArray& json,
                                  const QMap<QByteArray, QByteArray>& headers,
                                  int timeoutMs);

    QString googleTranslate(const QString& text, const QString& fromLang, const QString& toLang);
    QString deeplTranslate(const QString& text, const QString& fromLang, const QString& toLang);
    QString baiduTranslate(const QString& text, const QString& fromLang, const QString& toLang);
    QString bingTranslate(const QString& text, const QString& fromLang, const QString& toLang);
    QString aiTranslate(const QString& text, const QString& fromLang, const QString& toLang,
                        const QString& server);

    static bool isValidKey(const QString& key);

    // 配置
    QString m_baiduAppid;
    QString m_baiduSecretKey;
    QString m_deeplApiKey;
    QString m_googleApiKey;
    QString m_bingApiKey;
    QString m_bingRegion;
    QJsonObject m_aiConfigs;
};
