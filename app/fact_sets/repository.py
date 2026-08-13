"""默认不变事实文档的本地 JSON 仓库。"""

import asyncio
from datetime import datetime, timezone

from pydantic import ValidationError

from app.exceptions import StorageCorruptionError
from app.fact_sets.models import FactSet
from app.storage.json_file_store import JsonFileStore


class FactSetRepository:
    """原子读取和整体替换单个 FactSet JSON 文件。"""

    def __init__(self, file_path: str) -> None:
        if not file_path:
            raise ValueError("设定集存储路径不能为空")

        self.store = JsonFileStore(
            file_path=file_path,
            default_data=FactSet().model_dump(mode="json"),
        )
        self._lock = asyncio.Lock()

    async def load(self) -> FactSet:
        async with self._lock:
            data = await self.store.read()

        if not isinstance(data, dict):
            raise StorageCorruptionError("设定集文件根节点必须是对象")

        try:
            return FactSet.model_validate(data)
        except ValidationError as error:
            raise StorageCorruptionError(
                f"设定集文件数据无效：{error}"
            ) from None

    async def replace(self, content: str) -> FactSet:
        fact_set = FactSet(
            content=content,
            updated_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            await self.store.write(fact_set.model_dump(mode="json"))
        return fact_set
