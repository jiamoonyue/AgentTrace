"""从 .env 文件加载 LLM 配置。

为什么用 .env 而不是写死在代码里？
    1. API Key 是敏感信息, 不能提交到 Git
    2. 不同环境 (开发/测试/生产) 可能用不同的 Key
    3. 开源项目别人 clone 后自己创建 .env 就能跑

加载优先级:
    1. 系统环境变量 (最高)
    2. 项目根目录的 .env 文件
    3. 默认值
"""

import os


def _find_env_file() -> str | None:
    """向上查找项目根目录的 .env 文件。"""
    current = os.path.dirname(os.path.abspath(__file__))
    # 从 llm/ 目录向上找到 agenttrace 根目录
    for _ in range(5):
        env_path = os.path.join(current, ".env")
        if os.path.isfile(env_path):
            return env_path
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _load_dotenv() -> None:
    """手动解析 .env 文件, 不依赖 python-dotenv 库。

    格式: KEY=value (忽略注释和空行)
    """
    env_path = _find_env_file()
    if env_path is None:
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            # 解析 KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # 只在环境变量不存在时才设置 (环境变量优先级更高)
                if key not in os.environ:
                    os.environ[key] = value


# 模块加载时自动执行
_load_dotenv()


def get_deepseek_config() -> dict:
    """获取 DeepSeek 配置。"""
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    }
