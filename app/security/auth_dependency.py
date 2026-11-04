from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..common.exceptions import UnauthorizedException
from ..entity import User
from ..mapper.user_mapper import UserMapper
from ..util.jwt_util import parse_user_id

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    user_mapper: UserMapper = Depends(),
) -> User:
    """FastAPI 依赖：解析 Bearer 令牌并返回当前登录用户（≈ @AuthenticationPrincipal），无效或用户被禁用时返回 401。"""
    user_id = parse_user_id(credentials.credentials) if credentials else None
    user = user_mapper.select_by_id(user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise UnauthorizedException("未登录或登录已过期")
    return user
