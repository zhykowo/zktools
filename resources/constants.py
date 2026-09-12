import json
import sys
from pathlib import Path
from typing import Any

# 获取当前文件所在目录（根目录）
root_dir = Path(sys.argv[0]).resolve().parent


def load_config() -> dict[str, Any]:
    # 1. 检查 config_dev.json —— 开发/调试用，优先级最高
    dev_config = root_dir / "config_dev.json"
    if dev_config.exists():
        with open(dev_config, encoding="utf-8") as f:
            return json.load(f)

    # 2. 检查本地 config.json
    local_config = root_dir / "config.json"
    if local_config.exists():
        with open(local_config, encoding="utf-8") as f:
            return json.load(f)

    # 3. 都不存在时抛出异常
    raise FileNotFoundError("未找到任何配置文件，请在项目根目录放置 config_dev.json 或 config.json")


CONFIG = load_config()
