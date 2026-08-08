import httpx
import hashlib
import random
import json

from pathlib import Path

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

baidu_appid = CONFIG['translator']['apis']['baidu']['appid']
baidu_secret_key = CONFIG['translator']['apis']['baidu']['secret_key']

def baidu_translate(text, from_lang='auto', to_lang='zh'):
    salt = random.randint(1, 65536)
    # 拼接签名原文
    sign_str = baidu_appid + text + str(salt) + baidu_secret_key
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    
    # 请求参数
    url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'
    params = {
        'q': text,
        'from': from_lang,
        'to': to_lang,
        'appid': baidu_appid,
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

# 测试
print(baidu_translate('Hello, world!'))  # 输出