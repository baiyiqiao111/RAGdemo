from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class Document(Base):
    """文档表：知识库正文，通过 parent_id 组成目录树，支持乐观锁和软删除。"""
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_kb", "knowledge_base_id"),
        Index("ix_documents_parent_sort", "parent_id", "sort_order"),
        Index("ix_documents_creator", "creator_id"),
        Index("ix_documents_updated", "is_deleted", "updated_at"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        PK, ForeignKey("knowledge_bases.id"), nullable=False, comment="所属知识库，文档不能脱离知识库独立存在"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT, "mysql"), nullable=False, default="", comment="正文（Markdown）"
    )
    content_format: Mapped[str] = mapped_column(String(16), nullable=False, default="markdown", comment="正文格式")
    parent_id: Mapped[Optional[int]] = mapped_column(
        PK, ForeignKey("documents.id"), comment="父文档，NULL 为根节点（目录树）"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="同级排序")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="字数")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="正文 SHA-256，后续 RAG 判断是否需要重建向量")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="版本号，乐观锁防止并发覆盖")
    creator_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"), nullable=False, comment="创建人")
    updater_id: Mapped[int] = mapped_column(PK, ForeignKey("users.id"), nullable=False, comment="最后编辑人")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
