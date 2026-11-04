from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from ..config.settings import settings


def create_access_token(user_id: int) -> str:
    """为指定用户签发 JWT 访问令牌，过期时间取自配置。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def parse_user_id(token: str) -> Optional[int]:
    """解析令牌中的用户 id；签名错误、已过期或格式不对时返回 None。"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
