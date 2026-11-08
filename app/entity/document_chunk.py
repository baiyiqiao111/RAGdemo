from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class DocumentChunk(Base):
    """文档切片表：文档正文按长度切分后的片段，供后续 RAG 向量化/检索使用。"""
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document", "document_id", "chunk_index"),
        Index("ix_document_chunks_kb", "knowledge_base_id"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(PK, ForeignKey("documents.id"), nullable=False, comment="所属文档")
    knowledge_base_id: Mapped[int] = mapped_column(
        PK, ForeignKey("knowledge_bases.id"), nullable=False, comment="所属知识库，冗余自文档，便于检索时按库过滤"
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="在文档内的顺序，从 0 开始")
    content: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT, "mysql"), nullable=False, comment="切片正文"
    )
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="切片字符数")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
