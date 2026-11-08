from typing import Iterable, List

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import DocumentChunk


class DocumentChunkMapper:
    """document_chunks 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_document_id(self, document_id: int) -> List[DocumentChunk]:
        """按文档查询全部切片，按顺序排列。"""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(self.db.execute(stmt).scalars().all())

    def insert_many(self, chunks: List[DocumentChunk]) -> None:
        """批量新增切片。"""
        if chunks:
            self.db.add_all(chunks)
            self.db.flush()

    def delete_by_document_ids(self, document_ids: Iterable[int]) -> None:
        """按文档批量删除切片（文档被删除/重新切分时清理旧切片）。"""
        ids = list(document_ids)
        if ids:
            self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(ids)))
