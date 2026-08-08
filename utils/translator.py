import httpx
import hashlib
import random
from resources.constants import CONFIG

class Translator:
    def __init__(self):
        self.LANGUAGES = {
            "Auto": "auto",
            "English": "en",
            "Chinese": "zh",
            "Japanese": "ja",
            "Korean": "ko",
            "French": "fr",
            "German": "de",
            "Spanish": "es",
            "Russian": "ru"
        }

        self.baidu_appid = CONFIG['translator']['apis']['baidu']['appid']
        self.baidu_secret_key = CONFIG['translator']['apis']['baidu']['secret_key']

    def translate_text(self, text, from_lang='Auto', to_lang='Chinese', server='Baidu'):
        if server == 'Baidu':
            return self.baidu_translate(text=text, from_lang=from_lang, to_lang=to_lang)

    def baidu_translate(self, text, from_lang, to_lang):
        baidu_lang_code = {
            "Auto": "auto",
            "English": "en",
            "Chinese": "zh",
            "Japanese": "jp",
            "Korean": "kor",
            "French": "fra",
            "German": "de",
            "Spanish": "spa",
            "Russian": "ru"
        }
        from_lang = baidu_lang_code[from_lang]
        to_lang = baidu_lang_code[to_lang]

        salt = random.randint(1, 65536)
        # 拼接签名原文
        sign_str = self.baidu_appid + text + str(salt) + self.baidu_secret_key
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        # 请求参数
        url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'
        params = {
            'q': text,
            'from': from_lang,
            'to': to_lang,
            'appid': self.baidu_appid,
            'salt': salt,
            'sign': sign
        }
        
        response = httpx.post(url, data=params)
        result = response.json()
        
        # 解析结果
        if 'trans_result' in result:
            return result['trans_result'][0]['dst']
        else:
            return f"错误: {result}"