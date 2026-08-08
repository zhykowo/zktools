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