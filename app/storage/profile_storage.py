"""设定存储：key-value 结构，独立于消息存储"""

import os
import json
import logging
from typing import Dict

from app.exceptions import StorageCorruptionError, StorageIOError

logger = logging.getLogger(__name__)


class ProfileStorage:
    """设定存储（可拓展 key-value 结构）"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False)
        except OSError as e:
            raise StorageIOError(f"初始化设定文件失败: {e}") from None
        logger.debug(f"设定存储初始化完成：{file_path}")

    def load_profile(self) -> Dict[str, str]:
        """读取全部设定"""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            raise StorageCorruptionError("设定文件损坏，JSON 解析失败") from None
        except OSError as e:
            raise StorageIOError(f"读取设定文件失败: {e}") from None

    def save_profile(self, settings: Dict[str, str]) -> None:
        """全量覆盖保存设定"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except OSError as e:
            raise StorageIOError(f"写入设定文件失败: {e}") from None
        logger.debug(f"全量保存设定：共 {len(settings)} 项")

    def get_setting(self, key: str) -> str | None:
        """读取单个设定项"""
        settings = self.load_profile()
        return settings.get(key)

    def set_setting(self, key: str, value: str) -> None:
        """新增或修改单个设定项"""
        settings = self.load_profile()
        settings[key] = value
        self.save_profile(settings)
        logger.debug(f"设定项已更新：{key}")

    def delete_setting(self, key: str) -> None:
        """删除单个设定项"""
        settings = self.load_profile()
        if key in settings:
            del settings[key]
            self.save_profile(settings)
            logger.debug(f"设定项已删除：{key}")
        else:
            logger.debug(f"设定项不存在，跳过删除：{key}")