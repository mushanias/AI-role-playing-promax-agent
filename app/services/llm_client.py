"""LLM 客户端：封装调用 DeepSeek 的细节（异步）"""

import time
import logging
from typing import List, Dict
from openai import AsyncOpenAI
from openai import AuthenticationError, APIConnectionError, APITimeoutError

from app.exceptions import LLMAuthError, LLMNetworkError, LLMResponseError

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端，封装 DeepSeek 调用（异步）"""

    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化 openai SDK 异步客户端"""
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        logger.debug(f"LLM 客户端初始化完成，模型: {model}")

    async def chat(self, messages: List[Dict]) -> str:
        """调用 LLM 获取回复（异步）
        可能抛出:
            LLMAuthError: API Key 错误
            LLMNetworkError: 网络失败/超时
            LLMResponseError: 返回空回复
        """
        msg_count = len(messages)
        total_chars = sum(len(m["content"]) for m in messages)
        logger.debug(f"调用 LLM：{msg_count} 条消息，共 {total_chars} 字")

        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
        except AuthenticationError:
            # openai SDK 的认证错误 → 转成我们的自定义异常
            raise LLMAuthError("API Key 错误或失效，请检查 .env 中的 DEEPSEEK_API_KEY") from None
        except (APIConnectionError, APITimeoutError):
            # 网络连接或超时错误
            raise LLMNetworkError("网络连接失败或超时，请检查网络") from None

        elapsed = time.time() - start_time
        reply = response.choices[0].message.content

        # 检查回复是否为空
        if not reply:
            raise LLMResponseError("LLM 返回了空回复")

        logger.info(f"LLM 回复完成：耗时 {elapsed:.2f}s，回复 {len(reply)} 字")
        return reply
