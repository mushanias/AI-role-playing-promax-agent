"""本地认证服务与受保护路由依赖。"""

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from app.auth.service import LocalAuthService
from app.core.config import (
    LOCAL_AUTH_PASSWORD_HASH,
    LOCAL_AUTH_SESSION_TTL_SECONDS,
    LOCAL_AUTH_USERNAME,
)

LOCAL_AUTH_COOKIE_NAME = "local_session"


@lru_cache
def get_local_auth_service() -> LocalAuthService:
    """提供进程内唯一的本地认证与 Session 服务。"""
    return LocalAuthService(
        username=LOCAL_AUTH_USERNAME,
        password_hash=LOCAL_AUTH_PASSWORD_HASH,
        session_ttl_seconds=LOCAL_AUTH_SESSION_TTL_SECONDS,
    )


async def require_local_user(
    request: Request,
    service: LocalAuthService = Depends(get_local_auth_service),
) -> str:
    """拒绝没有有效 HttpOnly Session Cookie 的请求。"""
    token = request.cookies.get(LOCAL_AUTH_COOKIE_NAME)
    username = await service.get_username(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    return username
