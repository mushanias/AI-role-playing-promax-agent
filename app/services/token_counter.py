# app/services/token_counter.py
#token计数器，不是精确的所以要保存余量
from collections.abc import Sequence
from typing import Mapping

import tiktoken


class TokenCounter:
    """用于 Context 预算判断的 token 预估器。"""

    MESSAGE_OVERHEAD = 4
    REPLY_OVERHEAD = 2

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_text(self, text: str) -> int:
        """返回一段文本的预估 token 数。"""
        return len(self.encoding.encode(text))

    def count_messages(self, messages: Sequence[Mapping[str, str]]) -> int:
        """返回一组聊天消息的预估输入 token 数。"""
        total = self.REPLY_OVERHEAD

        for message in messages:
            total += self.MESSAGE_OVERHEAD
            total += self.count_text(message["content"])

        return total