"""LLM 客户端：封装调用 DeepSeek 的细节"""

import time
import logging
from typing import List, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端，封装 DeepSeek 调用"""

    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化 openai SDK 客户端"""
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        logger.debug(f"LLM 客户端初始化完成，模型: {model}")

    def chat(self, messages: List[Dict]) -> str:
        """调用 LLM 获取回复"""
        # 记录调用前信息：消息条数、总字数（不记完整内容，避免日志过大）
        msg_count = len(messages)
        total_chars = sum(len(m["content"]) for m in messages)
        logger.debug(f"调用 LLM：{msg_count} 条消息，共 {total_chars} 字")

        start_time = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        elapsed = time.time() - start_time
        reply = response.choices[0].message.content

        logger.info(f"LLM 回复完成：耗时 {elapsed:.2f}s，回复 {len(reply)} 字")
        return reply