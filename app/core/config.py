"""配置模块：从 .env 读取配置，集中暴露给其他模块"""

import os
from dotenv import load_dotenv

# 把项目根目录下的 .env 文件加载进环境变量
load_dotenv()

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 储存配置
STORAGE_PATH = os.getenv("STORAGE_PATH", "data/chat_history.json")
PROFILE_PATH = os.getenv("PROFILE_PATH", "data/profile.json")

# Context 管理配置
# APP_CONTEXT_BUDGET 是应用主动设定的单次上下文预算，不等于模型真实窗口
# 即使模型能装更多，应用仍主动控制成本和性能
APP_CONTEXT_BUDGET = int(os.getenv("APP_CONTEXT_BUDGET", "8000"))       # 应用上下文预算
OUTPUT_TOKEN_RESERVE = int(os.getenv("OUTPUT_TOKEN_RESERVE", "2000"))   # 预留输出 token
CONTEXT_SAFETY_MARGIN = int(os.getenv("CONTEXT_SAFETY_MARGIN", "200"))  # 安全余量
RECENT_TURNS_KEEP = int(os.getenv("RECENT_TURNS_KEEP", "6"))            # 最近保留几轮（完整轮次）

# 实际输入 token 预算 = 应用预算 - 输出预留 - 安全余量
INPUT_TOKEN_BUDGET = APP_CONTEXT_BUDGET - OUTPUT_TOKEN_RESERVE - CONTEXT_SAFETY_MARGIN

if INPUT_TOKEN_BUDGET <= 0:
    raise ValueError(
        "APP_CONTEXT_BUDGET 必须大于 OUTPUT_TOKEN_RESERVE + CONTEXT_SAFETY_MARGIN"
    )