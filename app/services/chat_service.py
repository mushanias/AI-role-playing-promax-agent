"""对话服务：编排读历史→ContextBuilder→调LLM→存消息的完整对话流程（异步）"""

import uuid
import logging
from datetime import datetime, timezone

from app.storage.base import BaseStorage
from app.services.llm_client import LLMClient
from app.services.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat()


class ChatService:
    """对话编排服务（异步）"""

    def __init__(
        self,
        storage: BaseStorage,
        llm_client: LLMClient,
        context_builder: ContextBuilder,
    ):
        """依赖注入
        Args:
            storage: 消息存储
            llm_client: LLM 客户端
            context_builder: 上下文构建器
        """
        self.storage = storage
        self.llm_client = llm_client
        self.context_builder = context_builder

    async def send(self, user_input: str, conversation_id: str = "default") -> str:
        """处理一轮对话（异步）
        Args:
            user_input: 用户输入的文本
            conversation_id: 会话 ID（MVP 默认 "default"）
        Returns:
            助手的回复文本
        """
        logger.debug(f"开始处理用户输入：{user_input[:20]}...")

        # 1. 存用户消息（带 message_id）
        user_message = {
            "message_id": str(uuid.uuid4()),
            "role": "user",
            "content": user_input,
            "timestamp": _utc_now_iso(),
        }
        await self.storage.save_message(user_message)

        # 2. 调 ContextBuilder 组装 messages（不再自己拼）
        llm_messages = await self.context_builder.build(conversation_id)

        # 3. 调 LLM
        reply = await self.llm_client.chat(llm_messages)

        # 4. 存助手回复（带 message_id）
        assistant_message = {
            "message_id": str(uuid.uuid4()),
            "role": "assistant",
            "content": reply,
            "timestamp": _utc_now_iso(),
        }
        await self.storage.save_message(assistant_message)

        logger.debug("一轮对话处理完成")
        return reply
