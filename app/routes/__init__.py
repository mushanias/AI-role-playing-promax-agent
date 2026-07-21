"""路由统一导出"""

from app.routes.chat import router as chat_router
from app.routes.profile import router as profile_router
from app.routes.conversations import router as conversations_router

__all__ = ["chat_router", "conversations_router", "profile_router"]
