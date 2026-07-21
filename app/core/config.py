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
CONVERSATIONS_PATH = os.getenv(
    "CONVERSATIONS_PATH",
    "data/conversations",
)

# Context 预算配置

# 这是应用主动设定的单轮总预算，不等于模型真实上下文窗口
APP_CONTEXT_BUDGET = int(os.getenv("APP_CONTEXT_BUDGET", "8000"))

# 为模型回复预留的 token 数
OUTPUT_TOKEN_RESERVE = int(os.getenv("OUTPUT_TOKEN_RESERVE", "2000"))

# 吸收 token 预估误差的安全余量
CONTEXT_SAFETY_MARGIN = int(os.getenv("CONTEXT_SAFETY_MARGIN", "200"))

# Context 本轮实际可发送给模型的输入预算
INPUT_TOKEN_BUDGET = (
    APP_CONTEXT_BUDGET
    - OUTPUT_TOKEN_RESERVE
    - CONTEXT_SAFETY_MARGIN
)

if INPUT_TOKEN_BUDGET <= 0:
    raise ValueError(
        "APP_CONTEXT_BUDGET 必须大于 "
        "OUTPUT_TOKEN_RESERVE + CONTEXT_SAFETY_MARGIN"
    )

CONTEXT_STATE_PATH = os.getenv(
    "CONTEXT_STATE_PATH",
    "data/context_state.json",
)

RECENT_TURNS_KEEP = int(
    os.getenv("RECENT_TURNS_KEEP", "6")
)

if RECENT_TURNS_KEEP < 1:
    raise ValueError("RECENT_TURNS_KEEP 必须大于 0")

SUMMARY_TOKEN_BUDGET = int(
    os.getenv("SUMMARY_TOKEN_BUDGET", "1000")
)

if SUMMARY_TOKEN_BUDGET <= 0:
    raise ValueError("SUMMARY_TOKEN_BUDGET 必须大于 0")

MAX_COMPRESSION_PASSES = int(
    os.getenv("MAX_COMPRESSION_PASSES", "3")
)

if MAX_COMPRESSION_PASSES < 1:
    raise ValueError("MAX_COMPRESSION_PASSES 必须大于 0")
