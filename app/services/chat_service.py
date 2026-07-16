"""对话服务：编排读历史→拼设定→调LLM→存消息的完整对话流程（异步）"""

import logging
from datetime import datetime
from typing import Dict
from uuid import uuid4

from app.storage.base import BaseStorage
from app.services.context_manager import ContextManager
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _new_message(role: str, content: str) -> Dict[str, str]:
    """创建一条带稳定身份标识的消息。"""
    return {
        "message_id": str(uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }


class ChatService:
    """对话编排服务（异步）"""

    def __init__(
        self,
        storage: BaseStorage,
        llm_client: LLMClient,
        context_manager: ContextManager,
    ) -> None:
        self.storage = storage
        self.llm_client = llm_client
        self.context_manager = context_manager

    async def send(self, user_input: str) -> str:
        """处理一轮对话（异步）"""
        logger.debug(f"开始处理用户输入：{user_input[:20]}...")

        # 1. 存用户消息
        await self.storage.save_message(_new_message("user", user_input))

        # 2. 由 ContextManager 组装可发送的上下文。
        context = await self.context_manager.build()
        reply = await self.llm_client.chat(context.messages)

        # 3. 存助手回复。
        await self.storage.save_message(_new_message("assistant", reply))

        logger.debug("一轮对话处理完成")
        return reply
