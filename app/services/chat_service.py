"""对话服务：编排读历史→调LLM→存消息的完整对话流程"""

from datetime import datetime
from typing import List, Dict

from app.storage.base import BaseStorage
from app.services.llm_client import LLMClient


class ChatService:
    """对话编排服务"""

    def __init__(self, storage: BaseStorage, llm_client: LLMClient):
        """依赖注入：传入储存实例和 LLM 客户端实例
        Args:
            storage: 储存实例（只要是 BaseStorage 子类即可，不绑定具体实现）
            llm_client: LLM 客户端实例
        """
        self.storage = storage
        self.llm_client = llm_client

    def send(self, user_input: str) -> str:
        """处理一轮对话
        Args:
            user_input: 用户输入的文本
        Returns:
            助手的回复文本
        """
        # 1. 存用户消息
        self.storage.save_message({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })

        # 2. 读全部历史消息
        all_messages = self.storage.load_messages()

        # 3. 剥离 timestamp，只保留 role 和 content（LLM 只认这两个字段）
        llm_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in all_messages
        ]

        # 4. 调 LLM 获取回复
        reply = self.llm_client.chat(llm_messages)

        # 5. 存助手回复
        self.storage.save_message({
            "role": "assistant",
            "content": reply,
            "timestamp": datetime.now().isoformat()
        })

        return reply