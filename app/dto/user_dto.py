from typing import Optional

from pydantic import BaseModel, Field


class UserRegisterDTO(BaseModel):
    """注册请求体。"""
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=72)  # bcrypt 最多 72 字节
    nickname: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)


class UserLoginDTO(BaseModel):
    """登录请求体。"""
    username: str
    password: str


class UserUpdateDTO(BaseModel):
    """更新个人资料请求体。"""
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
