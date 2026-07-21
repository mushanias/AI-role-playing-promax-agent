"""JSON 储存实现：把对话消息持久化到 JSON 文件（异步）"""
from app.storage.json_file_store import JsonFileStore
import logging
from typing import List, Dict

from app.storage.base import BaseStorage
from app.exceptions import StorageCorruptionError, StorageIOError

logger = logging.getLogger(__name__)


class JsonStorage(BaseStorage):
    """消息历史存储，只负责消息领域操作。"""

    def __init__(self, file_path: str):
        self.file_store = JsonFileStore(
            file_path=file_path,
            default_data=[],
        )
        #JsonStorage **拥有**一个 JSON 文件读写器，
        # 所以它通过 self.file_store 使用 JsonFileStore
        logger.debug(f"消息存储初始化完成：{file_path}")

    async def save_message(self, message: Dict) -> None:
        messages = await self.load_messages()
        messages.append(message)

        await self.file_store.write(messages)

        logger.debug(
            f"存入消息：role={message['role']}，"
            f"当前共 {len(messages)} 条"
        )

    async def load_messages(self) -> List[Dict]:
        data = await self.file_store.read()

        if not isinstance(data, list):
            raise StorageCorruptionError(
                "消息存储文件格式错误：根节点必须是列表"
            )

        return data

    async def clear_messages(self) -> None:
        await self.file_store.write([])
        logger.info("已清空全部消息")