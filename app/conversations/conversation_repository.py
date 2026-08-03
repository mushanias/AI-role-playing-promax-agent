"""单会话 JSON 仓库：持久化 Conversation 聚合对象。"""

import asyncio
import inspect
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List

from pydantic import ValidationError

from app.exceptions import (
    StorageConflictError,
    StorageCorruptionError,
    StorageIOError,
    StorageNotFoundError,
)
from app.conversations.conversation import Conversation
from app.storage.json_file_store import JsonFileStore

logger = logging.getLogger(__name__)

ConversationUpdater = Callable[[Conversation], Conversation]

_SAFE_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class DeletedConversationSnapshot:
    """回收站中的会话快照及其删除时间。"""

    conversation: Conversation
    deleted_at: datetime


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

    async def list_all(self) -> List[Conversation]:
        """加载存储目录中的全部合法会话快照。"""
        if not await asyncio.to_thread(
            os.path.isdir,
            self.base_directory,
        ):
            return []

        file_names = await asyncio.to_thread(
            os.listdir,
            self.base_directory,
        )
        conversation_ids = sorted(
            file_name.removesuffix(".json")
            for file_name in file_names
            if file_name.endswith(".json")
            and _SAFE_CONVERSATION_ID.fullmatch(
                file_name.removesuffix(".json")
            )
        )
        conversations = []
        for conversation_id in conversation_ids:
            conversations.append(await self.load(conversation_id))
        return conversations

    async def list_deleted(self) -> List[DeletedConversationSnapshot]:
        """加载回收站中的全部合法会话及文件删除时间。"""
        trash_directory = self._get_trash_directory()
        if not await asyncio.to_thread(os.path.isdir, trash_directory):
            return []

        file_names = await asyncio.to_thread(os.listdir, trash_directory)
        conversation_ids = sorted(
            file_name.removesuffix(".json")
            for file_name in file_names
            if file_name.endswith(".json")
            and _SAFE_CONVERSATION_ID.fullmatch(
                file_name.removesuffix(".json")
            )
        )
        snapshots = []
        for conversation_id in conversation_ids:
            file_path = self._get_trash_file_path(conversation_id)
            lock = self._get_lock(conversation_id)
            async with lock:
                try:
                    conversation = await self._load_unlocked(
                        conversation_id,
                        file_path,
                    )
                    modified_at = await asyncio.to_thread(
                        os.path.getmtime,
                        file_path,
                    )
                except StorageNotFoundError:
                    continue

            snapshots.append(
                DeletedConversationSnapshot(
                    conversation=conversation,
                    deleted_at=datetime.fromtimestamp(
                        modified_at,
                        tz=timezone.utc,
                    ),
                )
            )

        return snapshots

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

    async def delete(self, conversation_id: str) -> None:
        """把会话移动到回收站；不存在时保持 404 语义。"""
        file_path = self._get_file_path(conversation_id)
        trash_directory = self._get_trash_directory()
        trash_file_path = self._get_trash_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            if not await asyncio.to_thread(os.path.isfile, file_path):
                raise StorageNotFoundError(
                    f"会话不存在：{conversation_id}"
                )
            if await asyncio.to_thread(os.path.isfile, trash_file_path):
                raise StorageConflictError(
                    f"回收站中已存在会话：{conversation_id}"
                )

            try:
                await asyncio.to_thread(
                    os.makedirs,
                    trash_directory,
                    exist_ok=True,
                )
                await asyncio.to_thread(
                    os.rename,
                    file_path,
                    trash_file_path,
                )
            except FileNotFoundError:
                raise StorageNotFoundError(
                    f"会话不存在：{conversation_id}"
                ) from None
            except FileExistsError:
                raise StorageConflictError(
                    f"回收站中已存在会话：{conversation_id}"
                ) from None
            except OSError as error:
                raise StorageIOError(
                    f"删除会话失败：{conversation_id}；{error}"
                ) from None

            try:
                await asyncio.to_thread(os.utime, trash_file_path, None)
            except OSError:
                logger.warning(
                    "无法刷新会话删除时间：%s",
                    conversation_id,
                    exc_info=True,
                )

            logger.info("会话已移入回收站：%s", conversation_id)

    async def restore(self, conversation_id: str) -> None:
        """把回收站中的会话恢复到正常会话目录。"""
        file_path = self._get_file_path(conversation_id)
        trash_file_path = self._get_trash_file_path(conversation_id)
        lock = self._get_lock(conversation_id)

        async with lock:
            if not await asyncio.to_thread(
                os.path.isfile,
                trash_file_path,
            ):
                raise StorageNotFoundError(
                    f"回收站中不存在会话：{conversation_id}"
                )
            if await asyncio.to_thread(os.path.isfile, file_path):
                raise StorageConflictError(
                    f"正常会话中已存在同名会话：{conversation_id}"
                )

            try:
                await asyncio.to_thread(
                    os.rename,
                    trash_file_path,
                    file_path,
                )
            except FileNotFoundError:
                raise StorageNotFoundError(
                    f"回收站中不存在会话：{conversation_id}"
                ) from None
            except FileExistsError:
                raise StorageConflictError(
                    f"正常会话中已存在同名会话：{conversation_id}"
                ) from None
            except OSError as error:
                raise StorageIOError(
                    f"恢复会话失败：{conversation_id}；{error}"
                ) from None

            logger.info("从回收站恢复会话：%s", conversation_id)

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

    def _get_trash_directory(self) -> str:
        return os.path.join(self.base_directory, ".trash")

    def _get_trash_file_path(self, conversation_id: str) -> str:
        self._validate_conversation_id(conversation_id)
        return os.path.join(
            self._get_trash_directory(),
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
