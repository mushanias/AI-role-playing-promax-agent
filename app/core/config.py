"""配置模块：从 .env 读取配置，集中暴露给其他模块"""

import os
from dotenv import load_dotenv

# 把项目根目录下的 .env 文件加载进环境变量
load_dotenv()

# 存储配置
CONVERSATIONS_PATH = os.getenv(
    "CONVERSATIONS_PATH",
    "data/conversations",
)
PERFORMANCE_METRICS_PATH = os.getenv(
    "PERFORMANCE_METRICS_PATH",
    "data/performance.csv",
)
KNOWLEDGE_BASE_INDEX_PATH = os.getenv(
    "KNOWLEDGE_BASE_INDEX_PATH",
    "knowledge_base/indexes",
)
CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
)

# Context 预算配置：质量高水位 40k，压缩软目标 25k。
CONTEXT_SAFETY_MARGIN = int(os.getenv("CONTEXT_SAFETY_MARGIN", "200"))

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

CONTEXT_HIGH_WATERMARK = int(
    os.getenv("CONTEXT_HIGH_WATERMARK", "40000")
)
CONTEXT_LOW_WATERMARK = int(
    os.getenv("CONTEXT_LOW_WATERMARK", "25000")
)
RECENT_RAW_TOKEN_TARGET = int(
    os.getenv("RECENT_RAW_TOKEN_TARGET", "10000")
)

if CONTEXT_LOW_WATERMARK <= 0:
    raise ValueError("CONTEXT_LOW_WATERMARK 必须大于 0")
if CONTEXT_HIGH_WATERMARK <= CONTEXT_LOW_WATERMARK:
    raise ValueError("CONTEXT_HIGH_WATERMARK 必须大于低水位")
if not 0 < RECENT_RAW_TOKEN_TARGET < CONTEXT_LOW_WATERMARK:
    raise ValueError("RECENT_RAW_TOKEN_TARGET 必须处于 0 和低水位之间")
if CONTEXT_SAFETY_MARGIN < 0:
    raise ValueError("CONTEXT_SAFETY_MARGIN 不能小于 0")
