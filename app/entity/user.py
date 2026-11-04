from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class User(Base):
    """用户表：存储账号、密码哈希、角色等信息。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="登录名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 哈希")
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示名称")
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, comment="邮箱")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), comment="头像")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member", comment="admin / member")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后登录时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
