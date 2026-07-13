"""对话服务：编排读历史→调LLM→存消息的完整对话流程"""

import logging
from datetime import datetime
from typing import List, Dict

from app.storage.base import BaseStorage
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ChatService:
    """对话编排服务"""

    def __init__(self, storage: BaseStorage, llm_client: LLMClient):
        self.storage = storage
        self.llm_client = llm_client

    def send(self, user_input: str) -> str:
        """处理一轮对话"""
        logger.debug(f"开始处理用户输入：{user_input[:20]}...")  # 只记前20字

        # 1. 存用户消息
        self.storage.save_message({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })

        # 2. 读全部历史
        all_messages = self.storage.load_messages()

        # 3. 剥离 timestamp
        llm_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in all_messages
        ]

        # 4. 调 LLM
        reply = self.llm_client.chat(llm_messages)

        # 5. 存助手回复
        self.storage.save_message({
            "role": "assistant",
            "content": reply,
            "timestamp": datetime.now().isoformat()
        })

        logger.debug("一轮对话处理完成")
        return reply