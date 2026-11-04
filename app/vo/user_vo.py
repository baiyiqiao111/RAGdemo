from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserVO(BaseModel):
    """返回给前端的用户信息（不含密码哈希）。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    email: Optional[str]
    avatar_url: Optional[str]
    role: str
    created_at: datetime


class UserBriefVO(BaseModel):
    """用户简要信息，用于展示文档的创建人/编辑人。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str


class TokenVO(BaseModel):
    """登录成功的响应：访问令牌及当前用户信息。"""
    access_token: str
    token_type: str = "bearer"
    user: UserVO
