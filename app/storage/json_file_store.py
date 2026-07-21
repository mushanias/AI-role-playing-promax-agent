import asyncio
import copy
import json
import os
import tempfile
from typing import Any, Union

from app.exceptions import StorageCorruptionError, StorageIOError

JSONData = Union[dict[str, Any], list[Any]]


class JsonFileStore:
    """通用 JSON 文件读写器，只负责文件，不理解业务数据。"""

    def __init__(self, file_path: str, default_data: JSONData) -> None:
        self.file_path = file_path
        self.default_data = copy.deepcopy(default_data)

        directory = os.path.dirname(file_path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as error:
                raise StorageIOError(
                    f"初始化存储目录失败：{error}"
                ) from None

    async def read(self) -> JSONData:
        """读取 JSON 数据；文件不存在时返回默认值。"""

        def _read() -> JSONData:
            if not os.path.exists(self.file_path):
                return copy.deepcopy(self.default_data)

            try:
                with open(self.file_path, "r", encoding="utf-8") as file:
                    content = file.read().strip()

                if not content:
                    return copy.deepcopy(self.default_data)

                return json.loads(content)
            except json.JSONDecodeError:
                raise StorageCorruptionError(
                    "存储文件损坏，JSON 解析失败"
                ) from None
            except OSError as error:
                raise StorageIOError(
                    f"读取存储文件失败：{error}"
                ) from None

        return await asyncio.to_thread(_read)

    async def write(self, data: JSONData) -> None:
        """将 JSON 数据原子写入文件。"""

        def _write() -> None:
            directory = os.path.dirname(self.file_path) or "."
            temp_path = ""

            try:
                file_descriptor, temp_path = tempfile.mkstemp(
                    dir=directory,
                    suffix=".tmp",
                )

                with os.fdopen(
                    file_descriptor,
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())

                os.replace(temp_path, self.file_path)
            except (TypeError, ValueError) as error:
                raise StorageIOError(
                    f"JSON 数据无法写入：{error}"
                ) from None
            except OSError as error:
                raise StorageIOError(
                    f"写入存储文件失败：{error}"
                ) from None
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        await asyncio.to_thread(_write)
#通用工具