"""使用 Python 标准库生成并校验本地账号密码哈希。"""

import base64
import hashlib
import hmac
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 64
_MAX_MEMORY = 64 * 1024 * 1024


def hash_password(password: str, salt: bytes | None = None) -> str:
    """返回可直接保存到环境变量的 scrypt 密码哈希。"""
    if not password:
        raise ValueError("密码不能为空")

    actual_salt = salt or secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
        maxmem=_MAX_MEMORY,
    )
    salt_text = base64.urlsafe_b64encode(actual_salt).decode("ascii")
    key_text = base64.urlsafe_b64encode(derived_key).decode("ascii")
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}"
        f"${salt_text}${key_text}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """以常量时间比较用户输入与已保存的 scrypt 哈希。"""
    try:
        algorithm, n_text, r_text, p_text, salt_text, key_text = (
            encoded_hash.split("$", 5)
        )
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected_key = base64.urlsafe_b64decode(key_text.encode("ascii"))
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_text),
            r=int(r_text),
            p=int(p_text),
            dklen=len(expected_key),
            maxmem=_MAX_MEMORY,
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_key, expected_key)
