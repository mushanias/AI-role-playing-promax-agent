"""储存层抽象基类：定义统一契约，所有储存实现都必须遵守（异步）"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseStorage(ABC):
    """储存层抽象基类（异步）"""

    @abstractmethod
    async def save_message(self, message: Dict) -> None:
        """存一条消息（异步）
        Args:
            message: {"role": "user"/"assistant", "content": "...", "timestamp": "..."}
        """

    @abstractmethod
    async def load_messages(self) -> List[Dict]:
        """读取全部消息（异步）
        Returns:
            消息列表，如 [{"role": "user", "content": "你好", "timestamp": "..."}]
        """

    @abstractmethod
    async def clear_messages(self) -> None:
        """清空全部消息（异步）"""

# 目前使用json，后续更新，暴露的三个类。
