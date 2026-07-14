"""Token 计数器：封装 tiktoken，提供保守的 token 估算"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token 计数器

    当前使用 cl100k_base 编码和可配置的消息固定开销进行保守估算，
    不保证与 DeepSeek 服务端计数完全一致。
    实际用量以 API 响应中的 usage.prompt_tokens 为准。
    后续可拿真实 usage 值校准本地估算。
    """

    MESSAGE_OVERHEAD = 4   # 每条消息的固定开销（role/content 字段标记等）
    RESPONSE_OVERHEAD = 2  # 整体结尾标记开销

    def __init__(self, model: str = "deepseek-chat"):
        """初始化分词器
        Args:
            model: 模型名，用于日志记录
        """
        self.model = model
        # cl100k_base 对中英文都有较好覆盖，作为工程估算使用
        self.encoding = tiktoken.get_encoding("cl100k_base")
        logger.debug(f"TokenCounter 初始化完成，模型: {model}，编码: cl100k_base")

    def count(self, text: str) -> int:
        """计算一段文本的 token 数"""
        return len(self.encoding.encode(text))

    def count_messages(self, messages: Sequence[Mapping[str, Any]]) -> int:
        """估算 messages 列表的 token 数

        本地估算偏保守 + 保留安全余量 + 最终以 API usage 校准。
        """
        total = self.RESPONSE_OVERHEAD

        for message in messages:
            total += self.MESSAGE_OVERHEAD
            total += self.count(str(message.get("role", "")))
            total += self.count(str(message.get("content", "")))

        return total
