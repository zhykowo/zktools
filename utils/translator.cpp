#include "utils/translator.h"

#include "resources/constants.h"

#include <QCryptographicHash>
#include <QEventLoop>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QRandomGenerator>
#include <QTimer>
#include <QUrlQuery>
#include <QtGlobal>

namespace {

constexpr int kTimeoutMs = 15000;
constexpr int kAiTimeoutMs = 30000;

// 通用语言代码（ISO 639-1），多数服务直接使用；overrides 覆盖差异项
QString langCode(const QString& name, const QHash<QString, QString>& overrides,
                 const QString& fallback)
{
    const auto it = overrides.find(name);
    if (it != overrides.end())
        return it.value();
    static const QHash<QString, QString> common = {
        {QStringLiteral("Auto"),    QStringLiteral("auto")},
        {QStringLiteral("English"), QStringLiteral("en")},
        {QStringLiteral("Chinese"), QStringLiteral("zh")},
        {QStringLiteral("Japanese"),QStringLiteral("ja")},
        {QStringLiteral("Korean"),  QStringLiteral("ko")},
        {QStringLiteral("French"),  QStringLiteral("fr")},
        {QStringLiteral("German"),  QStringLiteral("de")},
        {QStringLiteral("Spanish"), QStringLiteral("es")},
        {QStringLiteral("Russian"), QStringLiteral("ru")},
    };
    return common.value(name, fallback);
}

// 简易 HTML 实体反转（对应 python html.unescape 的常用子集：
// 数字实体 + 常见命名实体，覆盖 Google v2 接口返回的 translatedText）
QString htmlUnescape(const QString& text)
{
    QString result;
    result.reserve(text.size());
    int i = 0;
    while (i < text.size()) {
        const QChar c = text.at(i);
        if (c != QLatin1Char('&')) {
            result.append(c);
            ++i;
            continue;
        }
        const int semi = text.indexOf(QLatin1Char(';'), i);
        if (semi < 0 || semi - i > 10) {   // 不成对或过长：按普通字符处理
            result.append(c);
            ++i;
            continue;
        }
        const QString entity = text.mid(i + 1, semi - i - 1);
        if (entity.startsWith(QLatin1Char('#'))) {
            bool ok = false;
            uint code = 0;
            if (entity.size() > 1 && (entity.at(1) == QLatin1Char('x') || entity.at(1) == QLatin1Char('X')))
                code = entity.mid(2).toUInt(&ok, 16);
            else
                code = entity.mid(1).toUInt(&ok, 10);
            if (ok && code > 0 && code < 0x110000) {
                // 单个码点（含增补平面）转 QString
                if (code <= 0xFFFF) {
                    result.append(QChar(char16_t(code)));
                } else {
                    const uint c = code - 0x10000;
                    result.append(QChar(char16_t(0xD800 + (c >> 10))));
                    result.append(QChar(char16_t(0xDC00 + (c & 0x3FF))));
                }
            } else
                result.append(text.mid(i, semi - i + 1));
        } else if (entity == QLatin1String("amp")) {
            result.append(QLatin1Char('&'));
        } else if (entity == QLatin1String("lt")) {
            result.append(QLatin1Char('<'));
        } else if (entity == QLatin1String("gt")) {
            result.append(QLatin1Char('>'));
        } else if (entity == QLatin1String("quot")) {
            result.append(QLatin1Char('"'));
        } else if (entity == QLatin1String("apos") || entity == QLatin1String("#39")) {
            result.append(QLatin1Char('\''));
        } else if (entity == QLatin1String("nbsp")) {
            result.append(QLatin1Char(' '));
        } else {
            result.append(text.mid(i, semi - i + 1));
        }
        i = semi + 1;
    }
    return result;
}

QByteArray percentEncodeForm(const QList<QPair<QString, QString>>& form)
{
    QUrlQuery q;
    q.setQueryItems(form);
    return q.toString(QUrl::FullyEncoded).toUtf8();
}

} // namespace

Translator::Translator()
{
    m_baiduAppid = AppConfig::instance().string(QStringLiteral("translator.apis.baidu.appid"));
    m_baiduSecretKey = AppConfig::instance().string(QStringLiteral("translator.apis.baidu.secret_key"));
    m_deeplApiKey = AppConfig::instance().string(QStringLiteral("translator.apis.deepl.api_key"));
    m_googleApiKey = AppConfig::instance().string(QStringLiteral("translator.apis.google.api_key"));
    m_bingApiKey = AppConfig::instance().string(QStringLiteral("translator.apis.bing.api_key"));
    m_bingRegion = AppConfig::instance().string(QStringLiteral("translator.apis.bing.region"));
    m_aiConfigs = AppConfig::instance().object(QStringLiteral("translator.apis.ai"));
}

bool Translator::isValidKey(const QString& key)
{
    const QString trimmed = key.trimmed();
    if (trimmed.isEmpty())
        return false;
    const QString lowered = trimmed.toLower();
    return !(lowered.startsWith(QStringLiteral("your_"))
             || lowered.startsWith(QStringLiteral("your-"))
             || lowered.startsWith(QLatin1Char('<'))
             || lowered == QStringLiteral("xxx"));
}

// ==================== 同步 HTTP ====================

Translator::HttpReply Translator::httpGet(const QUrl& url, int timeoutMs)
{
    HttpReply r;
    QNetworkAccessManager nam;
    QNetworkReply* reply = nam.get(QNetworkRequest(url));

    QEventLoop loop;
    QTimer timer;
    timer.setSingleShot(true);
    QObject::connect(&timer, &QTimer::timeout, &loop, &QEventLoop::quit);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    timer.start(timeoutMs);
    loop.exec();

    if (!reply->isFinished()) {
        reply->abort();
        r.error = QStringLiteral("timeout");
    } else if (reply->error() != QNetworkReply::NoError) {
        r.error = reply->errorString();
    } else {
        r.status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        r.body = reply->readAll();
    }
    delete reply;
    return r;
}

Translator::HttpReply Translator::httpPostForm(const QUrl& url,
                                               const QList<QPair<QString, QString>>& form,
                                               int timeoutMs)
{
    HttpReply r;
    QNetworkAccessManager nam;
    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader,
                      QStringLiteral("application/x-www-form-urlencoded"));
    QNetworkReply* reply = nam.post(request, percentEncodeForm(form));

    QEventLoop loop;
    QTimer timer;
    timer.setSingleShot(true);
    QObject::connect(&timer, &QTimer::timeout, &loop, &QEventLoop::quit);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    timer.start(timeoutMs);
    loop.exec();

    if (!reply->isFinished()) {
        reply->abort();
        r.error = QStringLiteral("timeout");
    } else if (reply->error() != QNetworkReply::NoError) {
        r.error = reply->errorString();
    } else {
        r.status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        r.body = reply->readAll();
    }
    delete reply;
    return r;
}

Translator::HttpReply Translator::httpPostJson(const QUrl& url, const QByteArray& json,
                                               const QMap<QByteArray, QByteArray>& headers,
                                               int timeoutMs)
{
    HttpReply r;
    QNetworkAccessManager nam;
    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, QByteArrayLiteral("application/json"));
    for (auto it = headers.begin(); it != headers.end(); ++it)
        request.setRawHeader(it.key(), it.value());
    QNetworkReply* reply = nam.post(request, json);

    QEventLoop loop;
    QTimer timer;
    timer.setSingleShot(true);
    QObject::connect(&timer, &QTimer::timeout, &loop, &QEventLoop::quit);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    timer.start(timeoutMs);
    loop.exec();

    if (!reply->isFinished()) {
        reply->abort();
        r.error = QStringLiteral("timeout");
    } else if (reply->error() != QNetworkReply::NoError) {
        r.error = reply->errorString();
    } else {
        r.status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        r.body = reply->readAll();
    }
    delete reply;
    return r;
}

// ==================== 分发入口 ====================

QString Translator::translateText(const QString& text, const QString& fromLang,
                                  const QString& toLang, const QString& server)
{
    const QString trimmed = text.trimmed();
    if (trimmed.isEmpty())
        return QString();

    QString result;
    if (server == QStringLiteral("Google"))
        result = googleTranslate(trimmed, fromLang, toLang);
    else if (server == QStringLiteral("DeepL"))
        result = deeplTranslate(trimmed, fromLang, toLang);
    else if (server == QStringLiteral("Baidu"))
        result = baiduTranslate(trimmed, fromLang, toLang);
    else if (server == QStringLiteral("Bing"))
        result = bingTranslate(trimmed, fromLang, toLang);
    else if (server == QStringLiteral("AI1") || server == QStringLiteral("AI2"))
        result = aiTranslate(trimmed, fromLang, toLang, server);
    else
        return QStringLiteral("错误: 未知的翻译服务 '%1'").arg(server);

    return result;
}

// ==================== Google ====================

QString Translator::googleTranslate(const QString& text, const QString& fromLang,
                                    const QString& toLang)
{
    static const QHash<QString, QString> overrides = {
        {QStringLiteral("Chinese"), QStringLiteral("zh-CN")},
    };
    const QString from = langCode(fromLang, overrides, QStringLiteral("auto"));
    const QString to = langCode(toLang, overrides, QStringLiteral("zh"));

    if (isValidKey(m_googleApiKey)) {
        // 付费官方 API（Google Cloud Translation v2）
        QUrl url(QStringLiteral("https://translation.googleapis.com/language/translate/v2"));
        QUrlQuery query;
        query.addQueryItem(QStringLiteral("q"), text);
        query.addQueryItem(QStringLiteral("source"), from);
        query.addQueryItem(QStringLiteral("target"), to);
        query.addQueryItem(QStringLiteral("format"), QStringLiteral("text"));
        query.addQueryItem(QStringLiteral("key"), m_googleApiKey);
        url.setQuery(query);

        const HttpReply r = httpPostForm(url, {}, kTimeoutMs);
        if (!r.ok())
            return QStringLiteral("翻译失败 (Google): %1").arg(r.error);

        const QJsonObject doc = QJsonDocument::fromJson(r.body).object();
        const QString translated = doc.value(QStringLiteral("data"))
                                       .toObject().value(QStringLiteral("translations"))
                                       .toArray().at(0).toObject()
                                       .value(QStringLiteral("translatedText")).toString();
        // v2 返回的 translatedText 含 HTML 实体（如 &#39;）
        return htmlUnescape(translated);
    }

    // 免费网页接口
    QUrl url(QStringLiteral("https://translate.googleapis.com/translate_a/single"));
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("client"), QStringLiteral("gtx"));
    query.addQueryItem(QStringLiteral("sl"), from);
    query.addQueryItem(QStringLiteral("tl"), to);
    query.addQueryItem(QStringLiteral("dt"), QStringLiteral("t"));
    query.addQueryItem(QStringLiteral("q"), text);
    url.setQuery(query);

    const HttpReply r = httpGet(url, kTimeoutMs);
    if (!r.ok())
        return QStringLiteral("翻译失败 (Google): %1").arg(r.error);

    const QJsonArray root = QJsonDocument::fromJson(r.body).array();
    QString out;
    const QJsonArray segments = root.at(0).toArray();
    for (const QJsonValue& seg : segments) {
        const QJsonArray pair = seg.toArray();
        if (pair.isEmpty())
            continue;
        if (pair.at(0).isString())
            out += pair.at(0).toString();
    }
    return out;
}

// ==================== DeepL ====================

QString Translator::deeplTranslate(const QString& text, const QString& fromLang,
                                   const QString& toLang)
{
    static const QHash<QString, QString> codes = {
        {QStringLiteral("Auto"),    QString()},       // 源语言缺省时由服务端自动检测
        {QStringLiteral("English"), QStringLiteral("EN")},
        {QStringLiteral("Chinese"), QStringLiteral("ZH")},
        {QStringLiteral("Japanese"),QStringLiteral("JA")},
        {QStringLiteral("Korean"),  QStringLiteral("KO")},
        {QStringLiteral("French"),  QStringLiteral("FR")},
        {QStringLiteral("German"),  QStringLiteral("DE")},
        {QStringLiteral("Spanish"), QStringLiteral("ES")},
        {QStringLiteral("Russian"), QStringLiteral("RU")},
    };
    const QString toCode = codes.value(toLang, QStringLiteral("#"));
    if (toCode.isNull() || toCode == QLatin1String("#"))
        return QStringLiteral("错误: DeepL 不支持目标语言 '%1'").arg(toLang);

    // 付费 key 优先走付费端点；未配置 / 占位 key / :fx 免费 key 走免费端点
    const bool paid = isValidKey(m_deeplApiKey)
                      && !m_deeplApiKey.toLower().endsWith(QStringLiteral(":fx"));
    const QUrl url(paid ? QStringLiteral("https://api.deepl.com/v2/translate")
                        : QStringLiteral("https://api-free.deepl.com/v2/translate"));

    QList<QPair<QString, QString>> form = {
        {QStringLiteral("auth_key"), m_deeplApiKey},
        {QStringLiteral("text"), text},
        {QStringLiteral("target_lang"), toCode},
    };
    const QString fromCode = codes.value(fromLang);
    if (!fromCode.isEmpty())
        form.append({QStringLiteral("source_lang"), fromCode});

    const HttpReply r = httpPostForm(url, form, kTimeoutMs);
    if (!r.ok())
        return QStringLiteral("翻译失败 (DeepL): %1").arg(r.error);
    if (r.status != 200) {
        const QJsonObject obj = QJsonDocument::fromJson(r.body).object();
        const QString message = obj.contains(QStringLiteral("message"))
                                    ? obj.value(QStringLiteral("message")).toString()
                                    : QString::fromUtf8(r.body);
        return QStringLiteral("错误: DeepL 请求失败 (%1) %2").arg(r.status).arg(message);
    }

    return QJsonDocument::fromJson(r.body).object()
        .value(QStringLiteral("translations")).toArray().at(0).toObject()
        .value(QStringLiteral("text")).toString();
}

// ==================== 百度 ====================

QString Translator::baiduTranslate(const QString& text, const QString& fromLang,
                                   const QString& toLang)
{
    if (m_baiduAppid.isEmpty() || m_baiduSecretKey.isEmpty())
        return QStringLiteral(
            "错误: 未配置百度翻译 key（config 的 translator.apis.baidu.appid / secret_key）");

    static const QHash<QString, QString> overrides = {
        {QStringLiteral("Japanese"), QStringLiteral("jp")},
        {QStringLiteral("Korean"),   QStringLiteral("kor")},
        {QStringLiteral("French"),   QStringLiteral("fra")},
        {QStringLiteral("Spanish"),  QStringLiteral("spa")},
    };
    const QString from = langCode(fromLang, overrides, QStringLiteral("auto"));
    const QString to = langCode(toLang, overrides, QStringLiteral("auto"));

    const int salt = QRandomGenerator::global()->bounded(1, 65537);
    const QString signStr = m_baiduAppid + text + QString::number(salt) + m_baiduSecretKey;
    const QString sign = QString::fromLatin1(
        QCryptographicHash::hash(signStr.toUtf8(), QCryptographicHash::Md5).toHex());

    const QUrl url(QStringLiteral("https://fanyi-api.baidu.com/api/trans/vip/translate"));
    const QList<QPair<QString, QString>> form = {
        {QStringLiteral("q"), text},
        {QStringLiteral("from"), from},
        {QStringLiteral("to"), to},
        {QStringLiteral("appid"), m_baiduAppid},
        {QStringLiteral("salt"), QString::number(salt)},
        {QStringLiteral("sign"), sign},
    };

    const HttpReply r = httpPostForm(url, form, kTimeoutMs);
    if (!r.ok())
        return QStringLiteral("翻译失败 (Baidu): %1").arg(r.error);

    const QJsonObject result = QJsonDocument::fromJson(r.body).object();
    if (result.contains(QStringLiteral("trans_result")))
        return result.value(QStringLiteral("trans_result")).toArray().at(0).toObject()
            .value(QStringLiteral("dst")).toString();
    // 错误码形式: {"error_code": "...", "error_msg": "..."}
    const QString errMsg = result.value(QStringLiteral("error_msg")).toString();
    return errMsg.isEmpty()
        ? QStringLiteral("错误: %1").arg(QString::fromUtf8(r.body))
        : QStringLiteral("错误: %1").arg(errMsg);
}

// ==================== Bing ====================

QString Translator::bingTranslate(const QString& text, const QString& fromLang,
                                  const QString& toLang)
{
    static const QHash<QString, QString> overrides = {
        {QStringLiteral("Chinese"), QStringLiteral("zh-Hans")},
    };
    const QString from = langCode(fromLang, overrides, QStringLiteral("auto"));
    const QString to = langCode(toLang, overrides, QStringLiteral("zh-Hans"));

    if (isValidKey(m_bingApiKey)) {
        // 付费官方 API（Azure Cognitive Services Translator）
        QUrl url(QStringLiteral("https://api.cognitive.microsofttranslator.com/translate"));
        QUrlQuery query;
        query.addQueryItem(QStringLiteral("from"), from);
        query.addQueryItem(QStringLiteral("to"), to);
        query.addQueryItem(QStringLiteral("api-version"), QStringLiteral("3.0"));
        url.setQuery(query);

        QMap<QByteArray, QByteArray> headers;
        headers.insert(QByteArrayLiteral("Ocp-Apim-Subscription-Key"), m_bingApiKey.toUtf8());
        if (!m_bingRegion.isEmpty())
            headers.insert(QByteArrayLiteral("Ocp-Apim-Subscription-Region"),
                           m_bingRegion.toUtf8());

        const QByteArray payload = QJsonDocument(QJsonArray{
            QJsonObject{{QStringLiteral("Text"), text}},
        }).toJson(QJsonDocument::Compact);

        const HttpReply r = httpPostJson(url, payload, headers, kTimeoutMs);
        if (!r.ok())
            return QStringLiteral("翻译失败 (Bing): %1").arg(r.error);
        return QJsonDocument::fromJson(r.body).array().at(0).toObject()
            .value(QStringLiteral("translations")).toArray().at(0).toObject()
            .value(QStringLiteral("text")).toString();
    }

    // 免费 Edge 接口
    const HttpReply auth = httpGet(QUrl(QStringLiteral("https://edge.microsoft.com/translate/auth")),
                                   kTimeoutMs);
    if (!auth.ok())
        return QStringLiteral("翻译失败 (Bing): %1").arg(auth.error);
    const QString token = QString::fromUtf8(auth.body).trimmed();

    QUrl url(QStringLiteral("https://api-edge.cognitive.microsofttranslator.com/translate"));
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("from"), from);
    query.addQueryItem(QStringLiteral("to"), to);
    query.addQueryItem(QStringLiteral("api-version"), QStringLiteral("3.0"));
    url.setQuery(query);

    QMap<QByteArray, QByteArray> headers;
    headers.insert(QByteArrayLiteral("Authorization"),
                   (QStringLiteral("Bearer ") + token).toUtf8());

    const QByteArray payload = QJsonDocument(QJsonArray{
        QJsonObject{{QStringLiteral("Text"), text}},
    }).toJson(QJsonDocument::Compact);

    const HttpReply r = httpPostJson(url, payload, headers, kTimeoutMs);
    if (!r.ok())
        return QStringLiteral("翻译失败 (Bing): %1").arg(r.error);
    return QJsonDocument::fromJson(r.body).array().at(0).toObject()
        .value(QStringLiteral("translations")).toArray().at(0).toObject()
        .value(QStringLiteral("text")).toString();
}

// ==================== AI1 / AI2（OpenAI 兼容 Chat API）====================

QString Translator::aiTranslate(const QString& text, const QString& fromLang,
                                const QString& toLang, const QString& server)
{
    const QJsonObject cfg = m_aiConfigs.value(server).toObject();
    if (cfg.isEmpty())
        return QStringLiteral("错误: 未配置 %1（config 的 translator.apis.ai.%1）").arg(server);

    const QString baseUrl = cfg.value(QStringLiteral("base_url")).toString();
    const QString apiKey = cfg.value(QStringLiteral("api_key")).toString();
    const QString model = cfg.value(QStringLiteral("model")).toString();
    if (baseUrl.isEmpty() || apiKey.isEmpty() || model.isEmpty())
        return QStringLiteral("错误: %1 配置不完整，需要 name/base_url/api_key/model").arg(server);

    const QString srcLabel = fromLang == QLatin1String("Auto")
                                 ? QStringLiteral("auto-detect")
                                 : fromLang;
    const QUrl url(baseUrl + (baseUrl.endsWith(QLatin1Char('/'))
                                  ? QStringLiteral("chat/completions")
                                  : QStringLiteral("/chat/completions")));

    QMap<QByteArray, QByteArray> headers;
    headers.insert(QByteArrayLiteral("Authorization"),
                   (QStringLiteral("Bearer ") + apiKey).toUtf8());

    const QJsonObject payload = QJsonObject{
        {QStringLiteral("model"), model},
        {QStringLiteral("messages"), QJsonArray{
            QJsonObject{
                {QStringLiteral("role"), QStringLiteral("system")},
                {QStringLiteral("content"),
                 QStringLiteral("You are a professional translation engine. Translate the user "
                                "input faithfully and return ONLY the translated text — no "
                                "explanations, notes, or surrounding quotes.")},
            },
            QJsonObject{
                {QStringLiteral("role"), QStringLiteral("user")},
                {QStringLiteral("content"),
                 QStringLiteral("Translate the following text from %1 to %2:\n\n%3")
                     .arg(srcLabel, toLang, text)},
            },
        }},
        {QStringLiteral("temperature"), 0.2},
    };

    const HttpReply r = httpPostJson(url, QJsonDocument(payload).toJson(QJsonDocument::Compact),
                                     headers, kAiTimeoutMs);
    if (!r.ok())
        return QStringLiteral("翻译失败 (%1): %2").arg(server, r.error);

    return QJsonDocument::fromJson(r.body).object()
        .value(QStringLiteral("choices")).toArray().at(0).toObject()
        .value(QStringLiteral("message")).toObject()
        .value(QStringLiteral("content")).toString().trimmed();
}
