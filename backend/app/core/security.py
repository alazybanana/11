"""安全基础设施：密码哈希与访问令牌。

本文件由 system 模块负责实现（见本文件原有约定），**只提供与具体业务无关的原语**：
- `hash_password` / `verify_password`：PBKDF2-HMAC-SHA256 密码哈希，数据库只存哈希；
- `create_access_token` / `decode_access_token`：HMAC-SHA256 签名的访问令牌。

实现上只使用 Python 标准库（`hashlib` / `hmac` / `base64` / `json`），
不引入 passlib、python-jose 等第三方依赖，避免为课程设计增加安装成本。

"当前登录用户"的 FastAPI 依赖项属于业务范畴，定义在
`app/modules/system/deps.py`，并由该模块的 `contract.py` 对外暴露给其它模块使用。
"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from app.core.config import settings

# ---------- 密码哈希 ---------- #
_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16


def hash_password(plain_password: str) -> str:
    """生成密码哈希，格式：`pbkdf2_sha256$迭代次数$盐$哈希`。"""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt, settings.PASSWORD_HASH_ITERATIONS
    )
    return "$".join(
        (
            _ALGORITHM,
            str(settings.PASSWORD_HASH_ITERATIONS),
            salt.hex(),
            digest.hex(),
        )
    )


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验密码。哈希串格式非法时返回 False，不抛异常。"""
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- 访问令牌 ---------- #
def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload_part: str) -> str:
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64encode(signature)


def create_access_token(user_id: int, username: str) -> tuple[str, int]:
    """签发访问令牌，返回 `(token, 有效期秒数)`。"""
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int((datetime.now() + timedelta(seconds=expires_in)).timestamp()),
    }
    payload_part = _b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    return f"{payload_part}.{_sign(payload_part)}", expires_in


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """解析并校验令牌。签名错误或已过期时返回 None。"""
    try:
        payload_part, signature = token.split(".")
    except ValueError:
        return None

    if not hmac.compare_digest(_sign(payload_part), signature):
        return None

    try:
        payload = json.loads(_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict) or payload.get("exp", 0) < datetime.now().timestamp():
        return None
    return payload
