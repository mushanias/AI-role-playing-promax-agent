"""请求级固定前缀的最小扩展契约。"""

from dataclasses import dataclass
from typing import Dict, Optional, Protocol, Tuple


@dataclass(frozen=True)
class ContextPrefixRequest:
    """固定前缀提供者可使用的当前请求信息。"""

    conversation_id: str
    branch_id: Optional[str]


class ContextPrefixProvider(Protocol):
    """为一次主对话请求提供零到多条固定前缀消息。"""

    async def get_messages(
        self,
        request: ContextPrefixRequest,
    ) -> Tuple[Dict[str, str], ...]:
        ...
