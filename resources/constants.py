import json
import os
import sys
from pathlib import Path

# 获取当前文件所在目录（根目录）
root_dir = Path(sys.argv[0]).resolve().parent

def _appdata_dir() -> Path:
    """返回 %APPDATA% 目录；非 Windows 环境回退到 ~/.config。"""
    appdata = os.environ.get('APPDATA')
    if appdata:
        return Path(appdata)
    return Path.home() / '.config'


def _appdata_config_path() -> Path:
    """返回 %APPDATA%\\zHyko\\zktools\\config.json"""
    return _appdata_dir() / 'zHyko' / 'zktools' / 'config.json'


def get_data_file_path(filename: str) -> Path:
    """返回用户数据文件路径，与配置文件的查找优先级保持一致：
    开发目录（存在 config_dev.json / config.json）放在项目根目录，
    打包环境放在 %APPDATA%\\zHyko\\zktools\\ 下（目录不存在时自动创建）。
    """
    if (root_dir / 'config_dev.json').exists() or (root_dir / 'config.json').exists():
        return root_dir / filename

    data_dir = _appdata_dir() / 'zHyko' / 'zktools'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / filename


def load_config() -> dict:
    # 1. 检查 config_dev.json —— 开发/调试用，优先级最高
    dev_config = root_dir / 'config_dev.json'
    if dev_config.exists():
        with open(dev_config, encoding='utf-8') as f:
            config = json.load(f)
        # 同步到 %APPDATA% 目录（创建或覆盖）
        appdata_path = _appdata_config_path()
        appdata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(appdata_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return config

    # 2. 同时检查 config.json 和 %APPDATA% 中的配置
    local_config = root_dir / 'config.json'
    appdata_config = _appdata_config_path()

    local_exists = local_config.exists()
    appdata_exists = appdata_config.exists()

    if local_exists and appdata_exists:
        # 双方都存在，使用时间更新的那一个
        if local_config.stat().st_mtime >= appdata_config.stat().st_mtime:
            with open(local_config, encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(appdata_config, encoding='utf-8') as f:
                return json.load(f)
    elif local_exists:
        # 只存在本地，复制到 %APPDATA%
        appdata_config.parent.mkdir(parents=True, exist_ok=True)
        with open(local_config, encoding='utf-8') as f:
            config = json.load(f)
        with open(appdata_config, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return config
    elif appdata_exists:
        # 只存在 %APPDATA%，复制到本地
        with open(appdata_config, encoding='utf-8') as f:
            config = json.load(f)
        with open(local_config, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return config
    else:
        # 双方都不存在
        raise FileNotFoundError(
            "未找到任何配置文件，请在项目根目录放置 config.json "
            "或 %APPDATA%\\zHyko\\zktools\\config.json"
        )


CONFIG = load_config()