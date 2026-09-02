"""翻译服务实现

支持服务：
- Google: 免费网页接口（无需 key）；配置 translator.apis.google.api_key 后优先走付费官方 API
- DeepL: 官方 API，配置有效付费 key 时优先走付费端点 api.deepl.com；
  未配置 / 占位 key / :fx 免费 key 时走免费端点 api-free.deepl.com
- Baidu: 官方 API，需 config 的 translator.apis.baidu.appid / secret_key
- Bing: 配置有效 key 时优先走 Azure 付费官方 API，否则走微软 Edge 免费接口
- AI1 / AI2: OpenAI 兼容 Chat API，base_url / api_key / model 以及按钮显示名
  均由 config 的 translator.apis.ai.<AI1|AI2> 指定

所有请求均带超时；translate_text 统一捕获异常并回显到结果框，避免中断 UI。
"""

import hashlib
import html
import random
from functools import partial

import httpx

from resources.constants import CONFIG


class Translator:
    # 通用语言代码（ISO 639-1），多数服务直接使用
    LANGUAGES = {
        "Auto": "auto",
        "English": "en",
        "Chinese": "zh",
        "Japanese": "ja",
        "Korean": "ko",
        "French": "fr",
        "German": "de",
        "Spanish": "es",
        "Russian": "ru",
    }

    # 百度专用语言代码
    BAIDU_LANG_CODES = {
        "Japanese": "jp",
        "Korean": "kor",
        "French": "fra",
        "Spanish": "spa",
    }

    # Google 专用语言代码（仅覆盖与通用代码不同的项）
    GOOGLE_LANG_CODES = {
        "Chinese": "zh-CN",
    }

    # DeepL 专用语言代码（目标语言必填大写；源语言缺省时由服务端自动检测）
    DEEPL_LANG_CODES = {
        "Auto": None,
        "English": "EN",
        "Chinese": "ZH",
        "Japanese": "JA",
        "Korean": "KO",
        "French": "FR",
        "German": "DE",
        "Spanish": "ES",
        "Russian": "RU",
    }

    # Bing 专用语言代码（仅覆盖与通用代码不同的项）
    BING_LANG_CODES = {
        "Chinese": "zh-Hans",
    }

    # AI 服务的内部标识符
    AI_SERVERS = ("AI1", "AI2")

    TIMEOUT = 15
    AI_TIMEOUT = 30

    def __init__(self):
        apis = CONFIG["translator"].get("apis", {})

        baidu = apis.get("baidu", {})
        self.baidu_appid = baidu.get("appid", "")
        self.baidu_secret_key = baidu.get("secret_key", "")

        self.deepl_api_key = apis.get("deepl", {}).get("api_key", "")

        self.google_api_key = apis.get("google", {}).get("api_key", "")

        bing = apis.get("bing", {})
        self.bing_api_key = bing.get("api_key", "")
        self.bing_region = bing.get("region", "")

        self.ai_configs = apis.get("ai", {})

    @staticmethod
    def _is_valid_key(key) -> bool:
        """判断 API key 是否真实可用：空值或 'your_xxx' 等占位符视为未配置"""
        if not key:
            return False
        key = str(key).strip()
        if not key:
            return False
        lowered = key.lower()
        return not (lowered.startswith(("your_", "your-", "<")) or lowered == "xxx")

    # ==================== 分发入口 ====================
    def translate_text(self, text, from_lang="Auto", to_lang="Chinese", server="Baidu"):
        """按服务标识符分发翻译；统一捕获异常，保证 UI 不崩溃"""
        text = (text or "").strip()
        if not text:
            return ""

        handlers = {
            "Google": self.google_translate,
            "DeepL": self.deepl_translate,
            "Baidu": self.baidu_translate,
            "Bing": self.bing_translate,
            "AI1": partial(self.ai_translate, server="AI1"),
            "AI2": partial(self.ai_translate, server="AI2"),
        }

        handler = handlers.get(server)
        if handler is None:
            return f"错误: 未知的翻译服务 '{server}'"

        try:
            return handler(text=text, from_lang=from_lang, to_lang=to_lang)
        except Exception as e:  # noqa: BLE001 —— 翻译失败回显到结果框而非中断 UI
            return f"翻译失败 ({server}): {e}"

    # ==================== Google（付费官方 API 优先，否则免费网页接口）====================
    def google_translate(self, text, from_lang, to_lang):
        from_lang = self.GOOGLE_LANG_CODES.get(from_lang) or self.LANGUAGES.get(
            from_lang, "auto"
        )
        to_lang = self.GOOGLE_LANG_CODES.get(to_lang) or self.LANGUAGES.get(
            to_lang, "zh"
        )

        if self._is_valid_key(self.google_api_key):
            # 付费官方 API（Google Cloud Translation v2）
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                "q": text,
                "source": from_lang,
                "target": to_lang,
                "format": "text",
                "key": self.google_api_key,
            }
            response = httpx.post(url, params=params, timeout=self.TIMEOUT)
            response.raise_for_status()
            # v2 返回的 translatedText 含 HTML 实体（如 &#39;）
            return html.unescape(
                response.json()["data"]["translations"][0]["translatedText"]
            )

        # 免费网页接口
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": from_lang, "tl": to_lang, "dt": "t", "q": text}

        response = httpx.get(url, params=params, timeout=self.TIMEOUT)
        response.raise_for_status()

        result = response.json()
        return "".join(seg[0] for seg in result[0] if seg and seg[0])

    # ==================== DeepL（付费端点优先，否则免费端点）====================
    def deepl_translate(self, text, from_lang, to_lang):
        to_code = self.DEEPL_LANG_CODES.get(to_lang)
        if not to_code:
            return f"错误: DeepL 不支持目标语言 '{to_lang}'"

        # 付费 key 优先走付费端点；未配置 / 占位 key / :fx 免费 key 走免费端点
        if self._is_valid_key(self.deepl_api_key) and not str(
            self.deepl_api_key
        ).lower().endswith(":fx"):
            url = "https://api.deepl.com/v2/translate"
        else:
            url = "https://api-free.deepl.com/v2/translate"

        data = {"auth_key": self.deepl_api_key, "text": text, "target_lang": to_code}
        from_code = self.DEEPL_LANG_CODES.get(from_lang)
        if from_code:
            data["source_lang"] = from_code

        response = httpx.post(url, data=data, timeout=self.TIMEOUT)
        if response.status_code != 200:
            try:
                message = response.json().get("message", response.text)
            except Exception:  # noqa: BLE001
                message = response.text
            return f"错误: DeepL 请求失败 ({response.status_code}) {message}"

        return response.json()["translations"][0]["text"]

    # ==================== 百度（官方 API，需 appid/secret_key）====================
    def baidu_translate(self, text, from_lang, to_lang):
        if not self.baidu_appid or not self.baidu_secret_key:
            return "错误: 未配置百度翻译 key（config 的 translator.apis.baidu.appid / secret_key）"

        from_lang = self.BAIDU_LANG_CODES.get(from_lang) or self.LANGUAGES.get(
            from_lang, "auto"
        )
        to_lang = self.BAIDU_LANG_CODES.get(to_lang) or self.LANGUAGES.get(
            to_lang, "auto"
        )

        salt = random.randint(1, 65536)
        # 拼接签名原文
        sign_str = self.baidu_appid + text + str(salt) + self.baidu_secret_key
        sign = hashlib.md5(sign_str.encode()).hexdigest()

        url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        params = {
            "q": text,
            "from": from_lang,
            "to": to_lang,
            "appid": self.baidu_appid,
            "salt": salt,
            "sign": sign,
        }

        response = httpx.post(url, data=params, timeout=self.TIMEOUT)
        response.raise_for_status()
        result = response.json()

        if "trans_result" in result:
            return result["trans_result"][0]["dst"]
        # 错误码形式: {"error_code": "...", "error_msg": "..."}
        return f"错误: {result.get('error_msg') or result}"

    # ==================== Bing（付费官方 API 优先，否则微软 Edge 免费接口）====================
    def bing_translate(self, text, from_lang, to_lang):
        from_lang = self.BING_LANG_CODES.get(from_lang) or self.LANGUAGES.get(
            from_lang, "auto"
        )
        to_lang = self.BING_LANG_CODES.get(to_lang) or self.LANGUAGES.get(
            to_lang, "zh-Hans"
        )

        if self._is_valid_key(self.bing_api_key):
            # 付费官方 API（Azure Cognitive Services Translator）
            url = "https://api.cognitive.microsofttranslator.com/translate"
            params = {"from": from_lang, "to": to_lang, "api-version": "3.0"}
            headers = {
                "Ocp-Apim-Subscription-Key": self.bing_api_key,
                "Content-Type": "application/json",
            }
            if self.bing_region:
                headers["Ocp-Apim-Subscription-Region"] = self.bing_region
            response = httpx.post(
                url,
                params=params,
                headers=headers,
                json=[{"Text": text}],
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            return response.json()[0]["translations"][0]["text"]

        # 免费 Edge 接口
        auth_response = httpx.get(
            "https://edge.microsoft.com/translate/auth", timeout=self.TIMEOUT
        )
        auth_response.raise_for_status()
        token = auth_response.text.strip()

        url = "https://api-edge.cognitive.microsofttranslator.com/translate"
        params = {"from": from_lang, "to": to_lang, "api-version": "3.0"}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = httpx.post(
            url,
            params=params,
            headers=headers,
            json=[{"Text": text}],
            timeout=self.TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        return result[0]["translations"][0]["text"]

    # ==================== AI1 / AI2（OpenAI 兼容 Chat API）====================
    def ai_translate(self, text, from_lang, to_lang, server="AI1"):
        cfg = self.ai_configs.get(server)
        if not cfg:
            return f"错误: 未配置 {server}（config 的 translator.apis.ai.{server}）"

        base_url = str(cfg.get("base_url") or "").rstrip("/")
        api_key = str(cfg.get("api_key") or "")
        model = str(cfg.get("model") or "")
        if not base_url or not api_key or not model:
            return f"错误: {server} 配置不完整，需要 name/base_url/api_key/model"

        src_label = "auto-detect" if from_lang == "Auto" else from_lang
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional translation engine. Translate the user input "
                        "faithfully and return ONLY the translated text — no explanations, notes, "
                        "or surrounding quotes."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Translate the following text from {src_label} to {to_lang}:\n\n{text}",
                },
            ],
            "temperature": 0.2,
        }

        response = httpx.post(
            url, headers=headers, json=payload, timeout=self.AI_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
