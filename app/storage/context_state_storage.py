from pydantic import ValidationError

from app.exceptions import StorageCorruptionError
from app.models.context_state import ContextState
from app.storage.json_file_store import JsonFileStore


class ContextStateStorage:
    """Context 派生状态的独立存储。"""

    def __init__(self, file_path: str):
        self.file_store = JsonFileStore(
            file_path=file_path,
            default_data={},
        )

    async def load(self) -> ContextState:
        data = await self.file_store.read()

        if not isinstance(data, dict):
            raise StorageCorruptionError(
                "Context 状态文件格式错误：根节点必须是对象"
            )

        try:
            return ContextState(**data)
        except ValidationError:
            raise StorageCorruptionError(
                "Context 状态文件格式错误：字段不符合 ContextState 定义"
            ) from None

    async def save(self, state: ContextState) -> None:
        await self.file_store.write(state.model_dump())

    async def clear(self) -> None:
        await self.file_store.write({})