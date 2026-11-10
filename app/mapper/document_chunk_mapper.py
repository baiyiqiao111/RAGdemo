from typing import Iterable, List

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config.database import SessionLocal, get_db
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

    def delete_by_knowledge_base_id(self, knowledge_base_id: int) -> None:
        """知识库被删除时，清理库内全部文档的切片（按知识库 id 直接删，不用逐个枚举文档）。"""
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.knowledge_base_id == knowledge_base_id))


def delete_chunks_by_document_ids_async(document_ids: Iterable[int]) -> None:
    """后台任务：异步删除这些文档的切片。

    用独立的数据库会话（而非请求里那个，响应返回后就关闭了），供 BackgroundTasks 调用。
    """
    ids = list(document_ids)
    if not ids:
        return
    db = SessionLocal()
    try:
        DocumentChunkMapper(db).delete_by_document_ids(ids)
        db.commit()
    finally:
        db.close()


def delete_chunks_by_knowledge_base_id_async(knowledge_base_id: int) -> None:
    """后台任务：异步删除某知识库下全部文档的切片，用独立的数据库会话，供 BackgroundTasks 调用。"""
    db = SessionLocal()
    try:
        DocumentChunkMapper(db).delete_by_knowledge_base_id(knowledge_base_id)
        db.commit()
    finally:
        db.close()
