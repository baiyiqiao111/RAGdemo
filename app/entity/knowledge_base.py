from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..config.database import Base
from .base_entity import PK


class KnowledgeBase(Base):
    """知识库表：文档的顶层归属，每个文档必须属于一个知识库。"""
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="知识库标题")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="知识库描述")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
