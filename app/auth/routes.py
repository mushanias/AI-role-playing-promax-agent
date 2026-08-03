"""单一本地账号登录、会话检查与退出接口。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import (
    LOCAL_AUTH_COOKIE_NAME,
    get_local_auth_service,
    require_local_user,
)
from app.auth.schemas import AuthSessionResponse, LoginRequest
from app.auth.service import LocalAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    request: LoginRequest,
    response: Response,
    service: LocalAuthService = Depends(get_local_auth_service),
) -> AuthSessionResponse:
    """验证固定账号，并写入只允许脚本外读取的 Session Cookie。"""
    token = await service.login(request.username, request.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    response.set_cookie(
        key=LOCAL_AUTH_COOKIE_NAME,
        value=token,
        max_age=service.session_ttl_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return AuthSessionResponse(
        authenticated=True,
        username=service.username,
    )


@router.get("/session", response_model=AuthSessionResponse)
async def get_session(
    username: str = Depends(require_local_user),
) -> AuthSessionResponse:
    """返回当前浏览器的本地登录状态。"""
    return AuthSessionResponse(authenticated=True, username=username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: LocalAuthService = Depends(get_local_auth_service),
) -> Response:
    """撤销当前 Session 并清除 Cookie。"""
    await service.logout(request.cookies.get(LOCAL_AUTH_COOKIE_NAME))
    response.delete_cookie(
        key=LOCAL_AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
