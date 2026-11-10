from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import Document


class DocumentMapper:
    """documents 表的数据访问对象，查询默认排除已软删除的记录。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, doc_id: int) -> Optional[Document]:
        """按主键查询文档（包含已删除的，由调用方判断 is_deleted）。"""
        return self.db.get(Document, doc_id)

    def select_alive_all(self, knowledge_base_id: int) -> List[Document]:
        """查询某知识库下全部未删除文档，按父文档、同级排序、id 排列，用于组装目录树。"""
        stmt = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id, Document.is_deleted.is_(False))
            .order_by(Document.parent_id, Document.sort_order, Document.id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def select_alive_child_ids(self, parent_ids: Iterable[int]) -> List[int]:
        """查询若干父文档下未删除的直接子文档 id。"""
        stmt = select(Document.id).where(
            Document.parent_id.in_(list(parent_ids)),
            Document.is_deleted.is_(False),
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_alive(self, keyword: Optional[str], knowledge_base_id: Optional[int], parent_id: Optional[int]) -> int:
        """按条件统计未删除文档数量。"""
        stmt = select(func.count(Document.id)).where(
            *self._alive_conditions(keyword, knowledge_base_id, parent_id)
        )
        return self.db.execute(stmt).scalar_one()

    def select_alive_page(
            self, keyword: Optional[str], knowledge_base_id: Optional[int], parent_id: Optional[int],
            offset: int, limit: int
    ) -> List[Document]:
        """按条件分页查询未删除文档，按更新时间倒序。"""
        stmt = (
            select(Document)
            .where(*self._alive_conditions(keyword, knowledge_base_id, parent_id))
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def insert(self, doc: Document) -> None:
        """新增文档，flush 后 doc.id 即可用。"""
        self.db.add(doc)
        self.db.flush()

    def update_by_id_and_version(
            self, doc_id: int, version: int, values: Dict[str, Any]
    ) -> int:
        """乐观锁更新：仅当版本号匹配且未删除时更新，并把 version + 1；返回受影响行数。"""
        stmt = (
            update(Document)
            .where(
                Document.id == doc_id,
                Document.version == version,
                Document.is_deleted.is_(False),
            )
            .values(**values, version=Document.version + 1)
        )

        result = self.db.execute(stmt)
        return result.rowcount

    def soft_delete_by_ids(self, ids: Iterable[int], deleted_at: datetime) -> int:
        """批量软删除，返回受影响行数。"""
        result = self.db.execute(
            update(Document).where(Document.id.in_(list(ids))).values(is_deleted=True, deleted_at=deleted_at)
        )
        return result.rowcount

    def soft_delete_by_knowledge_base_id(self, knowledge_base_id: int, deleted_at: datetime) -> int:
        """知识库被删除时，级联软删除库内全部文档，返回受影响行数。"""
        result = self.db.execute(
            update(Document)
            .where(Document.knowledge_base_id == knowledge_base_id, Document.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=deleted_at)
        )
        return result.rowcount

    def refresh(self, doc: Document) -> None:
        """从数据库重新加载实体，拿到 UPDATE 语句写入的最新值。"""
        self.db.refresh(doc)

    @staticmethod
    def _alive_conditions(keyword: Optional[str], knowledge_base_id: Optional[int], parent_id: Optional[int]) -> list:
        """拼装列表查询的 WHERE 条件（≈ MyBatis 动态 SQL 的 <where><if>）。"""
        conditions = [Document.is_deleted.is_(False)]
        if keyword:
            conditions.append(Document.title.contains(keyword))
        if knowledge_base_id is not None:
            conditions.append(Document.knowledge_base_id == knowledge_base_id)
        if parent_id is not None:
            conditions.append(Document.parent_id == parent_id)
        return conditions
