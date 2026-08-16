import json
import os
import sys
from pathlib import Path

# 获取当前文件所在目录（根目录）
root_dir = Path(sys.argv[0]).resolve().parent

# 默认配置模板，与开发目录下 config.json 内容一致
# （当所有候选配置文件都不存在时，用它创建 %APPDATA%\zHyko\PYDi\config.json）
DEFAULT_CONFIG = {
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
}


def _appdata_dir() -> Path:
    """返回 %APPDATA% 目录；非 Windows 环境回退到 ~/.config。"""
    appdata = os.environ.get('APPDATA')
    if appdata:
        return Path(appdata)
    return Path.home() / '.config'


def get_data_file_path(filename: str) -> Path:
    """返回用户数据文件路径，与配置文件的查找优先级保持一致：
    开发目录（存在 config_dev.json / config.json）放在项目根目录，
    打包环境放在 %APPDATA%\\zHyko\\PYDi\\ 下（目录不存在时自动创建）。
    """
    if (root_dir / 'config_dev.json').exists() or (root_dir / 'config.json').exists():
        return root_dir / filename

    data_dir = _appdata_dir() / 'zHyko' / 'PYDi'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / filename


def load_config() -> dict:
    # 按优先级依次尝试：config_dev.json -> config.json -> %APPDATA%\zHyko\PYDi\config.json
    candidates = [
        root_dir / 'config_dev.json',
        root_dir / 'config.json',
        _appdata_dir() / 'zHyko' / 'PYDi' / 'config.json',
    ]

    for path in candidates:
        if path.exists():
            with open(path, encoding='utf-8') as f:
                return json.load(f)

    # 全部不存在：创建 %APPDATA%\zHyko\PYDi\ 目录并写入默认配置
    appdata_config = candidates[-1]
    appdata_config.parent.mkdir(parents=True, exist_ok=True)
    with open(appdata_config, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=4)
    return DEFAULT_CONFIG


CONFIG = load_config()
