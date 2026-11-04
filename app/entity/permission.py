from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class Permission(Base):
    """权限表：用户对知识库/文档的访问权限申请与审批记录。"""
    __tablename__ = "permissions"
    __table_args__ = (
        Index("ix_permissions_target", "target_type", "target_id"),
        Index("ix_permissions_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"), nullable=False, comment="被授权用户")
    permission_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="read / write / admin")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="knowledge_base / document")
    target_id: Mapped[int] = mapped_column(PK, nullable=False, comment="知识库或文档 id（按 target_type 区分表）")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", comment="pending / approved / rejected"
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="申请时间")
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="审批时间")
    inviter_id: Mapped[Optional[int]] = mapped_column(
        PK, ForeignKey("users.id"), comment="邀请人：直接邀请的发起人，或自助申请被谁审批通过"
    )
