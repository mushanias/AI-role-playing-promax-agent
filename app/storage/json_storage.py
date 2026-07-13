"""JSON 储存实现：把对话消息持久化到 JSON 文件"""

import os
import json
import logging
from typing import List, Dict

from app.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class JsonStorage(BaseStorage):
    """JSON 文件储存实现"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
        logger.debug(f"储存初始化完成：{file_path}")

    def save_message(self, message: Dict) -> None:
        messages = self.load_messages()
        messages.append(message)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        logger.debug(f"存入消息：role={message['role']}，当前共 {len(messages)} 条")

    def load_messages(self) -> List[Dict]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            messages = json.loads(content)
            logger.debug(f"读取消息：共 {len(messages)} 条")
            return messages

    def clear_messages(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)
        logger.info("已清空全部消息")