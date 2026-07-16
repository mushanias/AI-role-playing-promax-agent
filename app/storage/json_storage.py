"""JSON 储存实现：把对话消息持久化到 JSON 文件（异步）"""

import os
import json
import logging
import asyncio
from typing import List, Dict

from app.storage.base import BaseStorage
from app.exceptions import StorageCorruptionError, StorageIOError

logger = logging.getLogger(__name__)


class JsonStorage(BaseStorage):
    """JSON 文件储存实现（异步）

    文件 IO 本身是同步的，这里用 asyncio.to_thread 把同步操作扔到线程池执行，
    避免阻塞 FastAPI 的事件循环。
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False)
        except OSError as e:
            raise StorageIOError(f"初始化储存文件失败: {e}") from None
        logger.debug(f"储存初始化完成：{file_path}")

    async def save_message(self, message: Dict) -> None:
        messages = await self.load_messages()
        messages.append(message)

        def _save():
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, KeyError):
                raise StorageCorruptionError("储存文件损坏，无法追加消息") from None
            except OSError as e:
                raise StorageIOError(f"写入储存文件失败: {e}") from None
            logger.debug(f"存入消息：role={message['role']}，当前共 {len(messages)} 条")

        await asyncio.to_thread(_save)

    async def load_messages(self) -> List[Dict]:
        def _load():
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    messages = json.loads(content)
            except json.JSONDecodeError:
                raise StorageCorruptionError("储存文件损坏，JSON 解析失败") from None
            except OSError as e:
                raise StorageIOError(f"读取储存文件失败: {e}") from None
            logger.debug(f"读取消息：共 {len(messages)} 条")
            return messages

        return await asyncio.to_thread(_load)

    async def clear_messages(self) -> None:
        def _clear():
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False)
            except OSError as e:
                raise StorageIOError(f"清空储存文件失败: {e}") from None
            logger.info("已清空全部消息")

        await asyncio.to_thread(_clear)
