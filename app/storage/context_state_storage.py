"""缓存状态存储：按会话隔离，原子写入，异步锁（异步）"""

import os
import re
import json
import logging
import asyncio
import tempfile
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import ValidationError

from app.models.context_state import ContextState
from app.exceptions import StorageCorruptionError, StorageIOError

logger = logging.getLogger(__name__)

# conversation_id 格式限制：字母、数字、下划线、短横线，1-64 字符
# 防止路径穿越攻击（如 ../../config）
_CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_conversation_id(conversation_id: str) -> None:
    """校验 conversation_id 格式，防止路径穿越"""
    if not _CONVERSATION_ID_PATTERN.fullmatch(conversation_id):
        raise ValueError(f"非法的 conversation_id: {conversation_id}")


class ContextStateStorage:
    """ContextState 的持久化存储（异步）

    - 按会话隔离：每个会话一个文件，路径为 {base_dir}/{conversation_id}.json
    - 原子写入：先写临时文件（flush+fsync），再 os.replace 重命名
    - 异步锁：同一会话的写操作串行化，防止并发覆盖
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        try:
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
        except OSError as e:
            raise StorageIOError(f"初始化缓存状态目录失败: {e}") from None
        logger.debug(f"缓存状态存储初始化完成：{base_dir}")

    def _get_file_path(self, conversation_id: str) -> str:
        """获取会话对应的文件路径（含格式校验）"""
        _validate_conversation_id(conversation_id)
        return os.path.join(self.base_dir, f"{conversation_id}.json")

    async def load(self, conversation_id: str) -> ContextState | None:
        """读取缓存状态；不存在则返回 None"""
        file_path = self._get_file_path(conversation_id)

        def _load():
            if not os.path.exists(file_path):
                return None
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return None
                    data = json.loads(content)
                    return ContextState.model_validate(data)
            except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as e:
                raise StorageCorruptionError(
                    f"缓存状态文件损坏或格式不兼容: {conversation_id}"
                ) from e
            except OSError as e:
                raise StorageIOError(f"读取缓存状态失败: {e}") from None

        state = await asyncio.to_thread(_load)
        logger.debug(f"读取缓存状态：{conversation_id}，{'有缓存' if state else '无缓存'}")
        return state

    async def save(self, conversation_id: str, state: ContextState) -> None:
        """保存缓存状态（原子写入 + 异步锁）"""
        # 校验会话 ID 一致性
        if state.conversation_id != conversation_id:
            raise ValueError(
                f"conversation_id 不一致: 参数={conversation_id}, "
                f"状态对象={state.conversation_id}"
            )

        file_path = self._get_file_path(conversation_id)

        # 不修改传入的 state，用 model_copy 生成带新时间戳的副本
        state_to_save = state.model_copy(
            update={"updated_at": datetime.now(timezone.utc)}
        )

        def _save():
            try:
                data = state_to_save.model_dump(mode="json")
                content = json.dumps(data, ensure_ascii=False, indent=2)
                # 原子写入：先写临时文件（flush+fsync），再重命名
                dir_path = os.path.dirname(file_path)
                fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
                    # os.replace 在 Windows/Linux 上都是原子操作
                    os.replace(tmp_path, file_path)
                except Exception:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise
            except OSError as e:
                raise StorageIOError(f"写入缓存状态失败: {e}") from None

        # 同一会话加锁，防止并发写覆盖
        async with self._locks[conversation_id]:
            await asyncio.to_thread(_save)
        logger.debug(
            f"保存缓存状态：{conversation_id}，摘要版本 v{state_to_save.summary_version}"
        )

    async def clear(self, conversation_id: str) -> None:
        """清除缓存状态"""
        file_path = self._get_file_path(conversation_id)

        def _clear():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as e:
                raise StorageIOError(f"清除缓存状态失败: {e}") from None

        async with self._locks[conversation_id]:
            await asyncio.to_thread(_clear)
        logger.info(f"已清除缓存状态：{conversation_id}")
