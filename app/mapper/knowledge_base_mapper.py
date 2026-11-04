from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import KnowledgeBase


class KnowledgeBaseMapper:
    """knowledge_bases 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, kb_id: int) -> Optional[KnowledgeBase]:
        """按主键查询知识库。"""
        return self.db.get(KnowledgeBase, kb_id)

    def select_all(self) -> List[KnowledgeBase]:
        """查询全部知识库，按创建时间倒序。"""
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def insert(self, kb: KnowledgeBase) -> None:
        """新增知识库，flush 后 kb.id 即可用。"""
        self.db.add(kb)
        self.db.flush()
