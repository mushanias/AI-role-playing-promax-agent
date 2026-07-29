"""全局角色设定存储：独立于会话生命周期。"""

from app.storage.json_file_store import JsonFileStore
import logging
from typing import Dict

from app.exceptions import StorageCorruptionError, StorageIOError

logger = logging.getLogger(__name__)


class ProfileStorage:
    """角色设定存储，只负责 key-value 设定操作。"""

    def __init__(self, file_path: str):
        self.file_store = JsonFileStore(
            file_path=file_path,
            default_data={},
        )
        logger.debug(f"角色设定存储初始化完成：{file_path}")

    async def load_profile(self) -> Dict[str, str]:
        data = await self.file_store.read()

        if not isinstance(data, dict):
            raise StorageCorruptionError(
                "角色设定文件格式错误：根节点必须是对象"
            )

        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in data.items()
        ):
            raise StorageCorruptionError(
                "角色设定文件格式错误：键和值必须是字符串"
            )

        return data

    async def save_profile(self, settings: Dict[str, str]) -> None:
        await self.file_store.write(settings)
        logger.debug(f"保存角色设定：共 {len(settings)} 项")

    async def get_setting(self, key: str) -> str | None:
        settings = await self.load_profile()
        return settings.get(key)

    async def set_setting(self, key: str, value: str) -> None:
        settings = await self.load_profile()
        settings[key] = value
        await self.save_profile(settings)

    async def delete_setting(self, key: str) -> None:
        settings = await self.load_profile()

        if key in settings:
            del settings[key]
            await self.save_profile(settings)
