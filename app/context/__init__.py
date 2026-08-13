"""跨业务模块共享的模型 Context 契约。"""

from app.context.prefix import (
    ContextPrefixProvider,
    ContextPrefixRequest,
)

__all__ = [
    "ContextPrefixProvider",
    "ContextPrefixRequest",
]
