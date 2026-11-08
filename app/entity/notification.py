from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class Notification(Base):
    """系统通知表：目前用于权限申请的待办提醒，点进去可直接审批。"""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user", "user_id", "is_read"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"), nullable=False, comment="接收通知的用户")
    permission_id: Mapped[Optional[int]] = mapped_column(
        PK, ForeignKey("permissions.id"), comment="关联的权限申请，用于点进去直接审批"
    )
    target_type: Mapped[Optional[str]] = mapped_column(String(16), comment="knowledge_base / document，冗余自权限申请")
    target_id: Mapped[Optional[int]] = mapped_column(PK, comment="知识库或文档 id，冗余自权限申请")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="通知标题")
    content: Mapped[Optional[str]] = mapped_column(Text, comment="通知内容")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已读")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
