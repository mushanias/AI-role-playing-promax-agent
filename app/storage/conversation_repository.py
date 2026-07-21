"""单会话 JSON 仓库：持久化 Conversation 聚合对象。"""

import asyncio
import inspect
import logging
import os
import re
from typing import Callable, Dict

from pydantic import ValidationError

from app.exceptions import (
    StorageConflictError,
    StorageCorruptionError,
    StorageNotFoundError,
)
from app.models.conversation import Conversation
from app.storage.json_file_store import JsonFileStore

logger = logging.getLogger(__name__)

ConversationUpdater = Callable[[Conversation], Conversation]

_SAFE_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ConversationRepository:
    """以一个 JSON 文件为单位读写单个会话。"""

    def __init__(self, base_directory: str) -> None:
        if not base_directory:
            raise ValueError("会话存储目录不能为空")

        self.base_directory = base_directory
        self._locks: Dict[str, asyncio.Lock] = {}

    async def exists(self, conversation_id: str) -> bool:
        """返回指定会话文件是否存在。"""
        file_path = self._get_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            return await asyncio.to_thread(os.path.isfile, file_path)

    async def create(self, conversation: Conversation) -> None:
        """创建新会话；禁止覆盖已经存在的会话文件。"""
        conversation_id = conversation.conversation_id
        file_path = self._get_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            if await asyncio.to_thread(os.path.isfile, file_path):
                raise StorageConflictError(
                    f"会话已存在：{conversation_id}"
                )

            validated = self._validate_snapshot(conversation)
            await self._write(file_path, validated)
            logger.debug("创建会话：%s", conversation_id)

    async def load(self, conversation_id: str) -> Conversation:
        """加载并校验指定会话。"""
        file_path = self._get_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            return await self._load_unlocked(conversation_id, file_path)

    async def save(self, conversation: Conversation) -> None:
        """完整替换一个已经存在的合法会话快照。"""
        conversation_id = conversation.conversation_id
        file_path = self._get_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            if not await asyncio.to_thread(os.path.isfile, file_path):
                raise StorageNotFoundError(
                    f"会话不存在：{conversation_id}"
                )

            validated = self._validate_snapshot(conversation)
            await self._write(file_path, validated)
            logger.debug("保存会话：%s", conversation_id)

    async def update(
        self,
        conversation_id: str,
        updater: ConversationUpdater,
    ) -> Conversation:
        """在单会话锁内完成加载、内存变更、校验和原子保存。"""
        if not callable(updater):
            raise TypeError("updater 必须是可调用对象")

        file_path = self._get_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            current = await self._load_unlocked(
                conversation_id,
                file_path,
            )
            working_copy = current.model_copy(deep=True)
            updated = updater(working_copy)

            if inspect.isawaitable(updated):
                if inspect.iscoroutine(updated):
                    updated.close()
                raise TypeError("updater 必须是同步函数")
            if not isinstance(updated, Conversation):
                raise TypeError("updater 必须返回 Conversation")

            validated = self._validate_snapshot(updated)
            if validated.conversation_id != conversation_id:
                raise ValueError("updater 不能修改 conversation_id")

            await self._write(file_path, validated)
            logger.debug("更新会话：%s", conversation_id)
            return validated

    async def _load_unlocked(
        self,
        conversation_id: str,
        file_path: str,
    ) -> Conversation:
        if not await asyncio.to_thread(os.path.isfile, file_path):
            raise StorageNotFoundError(f"会话不存在：{conversation_id}")

        data = await self._get_store(file_path).read()
        if not isinstance(data, dict):
            raise StorageCorruptionError(
                f"会话文件格式错误，根节点必须是对象：{conversation_id}"
            )

        try:
            conversation = Conversation.model_validate(data)
        except ValidationError as error:
            raise StorageCorruptionError(
                f"会话文件数据无效：{conversation_id}；{error}"
            ) from None

        if conversation.conversation_id != conversation_id:
            raise StorageCorruptionError(
                "会话文件名与文件内 conversation_id 不一致"
            )

        return conversation

    async def _write(
        self,
        file_path: str,
        conversation: Conversation,
    ) -> None:
        await self._get_store(file_path).write(
            conversation.model_dump(mode="json")
        )

    @staticmethod
    def _validate_snapshot(conversation: Conversation) -> Conversation:
        if not isinstance(conversation, Conversation):
            raise TypeError("conversation 必须是 Conversation")

        return Conversation.model_validate(
            conversation.model_dump(mode="python")
        )

    def _get_file_path(self, conversation_id: str) -> str:
        self._validate_conversation_id(conversation_id)
        return os.path.join(
            self.base_directory,
            f"{conversation_id}.json",
        )

    def _get_lock(self, conversation_id: str) -> asyncio.Lock:
        lock = self._locks.get(conversation_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[conversation_id] = lock
        return lock

    @staticmethod
    def _get_store(file_path: str) -> JsonFileStore:
        return JsonFileStore(file_path=file_path, default_data={})

    @staticmethod
    def _validate_conversation_id(conversation_id: str) -> None:
        if not _SAFE_CONVERSATION_ID.fullmatch(conversation_id):
            raise ValueError(
                "conversation_id 只能包含字母、数字、下划线和连字符"
            )
