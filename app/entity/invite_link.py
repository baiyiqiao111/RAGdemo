from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class InviteLink(Base):
    """邀请链接：分享给单个用户，登录后点开自动获得指定的知识库/文档权限，仅能兑换一次。"""
    __tablename__ = "invite_links"
    __table_args__ = (
        Index("ix_invite_links_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(43), nullable=False, unique=True, comment="邀请令牌，拼在邀请链接里")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="knowledge_base / document")
    target_id: Mapped[int] = mapped_column(PK, nullable=False, comment="知识库或文档 id")
    permission_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="read / write / admin")
    created_by: Mapped[int] = mapped_column(PK, ForeignKey("users.id"), nullable=False, comment="创建者")
    permission_id: Mapped[Optional[int]] = mapped_column(
        PK, ForeignKey("permissions.id"), comment="兑换后绑定的权限记录，NULL 表示尚未被使用"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="过期时间，NULL 为永不过期")
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已撤销")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
