"""固定本地账号与进程内 Session 生命周期。"""

import asyncio
import hmac
import secrets
from time import monotonic

from app.auth.password import verify_password


class LocalAuthService:
    """验证单一账号，并保存后端重启即失效的内存 Session。"""

    def __init__(
        self,
        username: str,
        password_hash: str,
        session_ttl_seconds: int,
    ) -> None:
        if not username or not password_hash:
            raise ValueError("本地登录账号和密码哈希不能为空")
        if session_ttl_seconds <= 0:
            raise ValueError("Session 有效期必须大于 0")

        self.username = username
        self.password_hash = password_hash
        self.session_ttl_seconds = session_ttl_seconds
        self._sessions: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def login(self, username: str, password: str) -> str | None:
        """验证账号，成功时返回不可预测的 Session Token。"""
        password_matches = verify_password(password, self.password_hash)
        username_matches = hmac.compare_digest(
            username.encode("utf-8"),
            self.username.encode("utf-8"),
        )
        if not password_matches or not username_matches:
            return None

        token = secrets.token_urlsafe(32)
        expires_at = monotonic() + self.session_ttl_seconds
        async with self._lock:
            self._remove_expired_sessions()
            self._sessions[token] = expires_at
        return token

    async def get_username(self, token: str | None) -> str | None:
        """返回有效 Session 对应的固定用户名。"""
        if not token:
            return None

        async with self._lock:
            self._remove_expired_sessions()
            if token not in self._sessions:
                return None
        return self.username

    async def logout(self, token: str | None) -> None:
        """撤销一个 Session；Token 不存在时保持幂等。"""
        if not token:
            return
        async with self._lock:
            self._sessions.pop(token, None)

    def _remove_expired_sessions(self) -> None:
        now = monotonic()
        expired_tokens = [
            token
            for token, expires_at in self._sessions.items()
            if expires_at <= now
        ]
        for token in expired_tokens:
            self._sessions.pop(token, None)
