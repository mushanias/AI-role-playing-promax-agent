"""路由统一导出。"""

from app.routes.profile import router as profile_router
from app.routes.conversations import router as conversations_router

__all__ = ["conversations_router", "profile_router"]
