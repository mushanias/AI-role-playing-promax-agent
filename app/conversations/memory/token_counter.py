"""会话 Context 使用的 Token 预估器。"""

# Token 计数不是绝对精确值，因此预算需要保留安全余量。
from collections.abc import Sequence
from typing import Mapping


class TokenCounter:
    """用于 Context 预算判断的 token 预估器。"""

    MESSAGE_OVERHEAD = 4
    REPLY_OVERHEAD = 2

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        # 延迟加载二进制依赖，读取历史等非 LLM 请求无需初始化分词器。
        import tiktoken

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
