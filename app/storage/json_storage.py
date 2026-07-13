"""JSON 储存实现：把对话消息持久化到 JSON 文件"""

import os
import json
from typing import List, Dict

from app.storage.base import BaseStorage


class JsonStorage(BaseStorage):
    """JSON 文件储存实现"""

    def __init__(self, file_path: str):
        """初始化，确保文件和目录存在
        Args:
            file_path: 储存文件路径，如 "data/chat_history.json"
        """
        self.file_path = file_path
        # 确保目录存在（os.path.dirname 取父目录路径）
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        # 确保文件存在（不存在就建一个空 JSON 文件）
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

    def save_message(self, message: Dict) -> None:
        """存一条消息：读旧 → 追加 → 写回"""
        messages = self.load_messages()
        messages.append(message)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    def load_messages(self) -> List[Dict]:
        """读取全部消息；文件为空时返回空列表"""
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)

    def clear_messages(self) -> None:
        """清空全部消息（写回空列表）"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)