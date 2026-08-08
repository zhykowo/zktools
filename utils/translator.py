import httpx
import hashlib
import random
import json

from pathlib import Path

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

        # 获取当前文件所在目录（根目录）
        root_dir = Path.cwd()

        # 构建配置文件路径
        dev_config_path = root_dir / 'config_dev.json'
        default_config_path = root_dir / 'config.json'

        # 选择配置文件
        if dev_config_path.exists():
            config_path = dev_config_path
        else:
            config_path = default_config_path

        with open(config_path, encoding='utf-8') as f:
            CONFIG = json.load(f)

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