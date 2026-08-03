"""本地登录 HTTP 数据契约。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    username: str
