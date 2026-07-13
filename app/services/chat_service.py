"""对话服务：编排读历史→拼设定→调LLM→存消息的完整对话流程（异步）"""

import logging
from datetime import datetime
from typing import List, Dict

from app.storage.base import BaseStorage
from app.storage.profile_storage import ProfileStorage
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ChatService:
    """对话编排服务（异步）"""

    def __init__(
        self,
        storage: BaseStorage,
        llm_client: LLMClient,
        profile_storage: ProfileStorage,
    ):
        """依赖注入
        Args:
            storage: 消息存储
            llm_client: LLM 客户端
            profile_storage: 设定存储
        """
        self.storage = storage
        self.llm_client = llm_client
        self.profile_storage = profile_storage

    async def send(self, user_input: str) -> str:
        """处理一轮对话（异步）"""
        logger.debug(f"开始处理用户输入：{user_input[:20]}...")

        # 1. 存用户消息
        await self.storage.save_message({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })

        # 2. 读全部历史
        all_messages = await self.storage.load_messages()

        # 3. 剥离 timestamp，组装发给 LLM 的消息列表
        llm_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in all_messages
        ]

        # 4. 读设定，拼成 system message，插到最前
        settings = await self.profile_storage.load_profile()
        if settings:
            system_content = "\n\n".join(
                f"【{key}】\n{value}" for key, value in settings.items()
            )
            llm_messages = [{"role": "system", "content": system_content}] + llm_messages
            logger.debug(f"已注入设定：共 {len(settings)} 项")
        else:
            logger.debug("无设定，裸对话")

        # 5. 调 LLM
        reply = await self.llm_client.chat(llm_messages)

        # 6. 存助手回复
        await self.storage.save_message({
            "role": "assistant",
            "content": reply,
            "timestamp": datetime.now().isoformat()
        })

        logger.debug("一轮对话处理完成")
        return reply
