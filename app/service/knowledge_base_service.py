from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import NotFoundException
from ..config.database import get_db
from ..dto.knowledge_base_dto import KnowledgeBaseCreateDTO
from ..entity import KnowledgeBase
from ..mapper.knowledge_base_mapper import KnowledgeBaseMapper
from ..vo.knowledge_base_vo import KnowledgeBaseVO


class KnowledgeBaseService:
    """知识库相关业务：文档的顶层归属容器。"""

    def __init__(self, db: Session = Depends(get_db), knowledge_base_mapper: KnowledgeBaseMapper = Depends()):
        """构造器注入数据库会话（用于提交事务）和 KnowledgeBaseMapper。"""
        self.db = db
        self.knowledge_base_mapper = knowledge_base_mapper

    def list_all(self) -> List[KnowledgeBaseVO]:
        """返回全部知识库，按创建时间倒序。"""
        return [KnowledgeBaseVO.model_validate(kb) for kb in self.knowledge_base_mapper.select_all()]

    def create(self, dto: KnowledgeBaseCreateDTO) -> KnowledgeBaseVO:
        """新建知识库。"""
        kb = KnowledgeBase(title=dto.title, description=dto.description)
        self.knowledge_base_mapper.insert(kb)
        self.db.commit()
        return KnowledgeBaseVO.model_validate(kb)

    def detail(self, kb_id: int) -> KnowledgeBaseVO:
        """获取知识库详情，不存在抛 404。"""
        return KnowledgeBaseVO.model_validate(self.get_alive(kb_id))

    def get_alive(self, kb_id: int) -> KnowledgeBase:
        """按 id 获取知识库实体，不存在抛 404；供 DocumentService 校验归属。"""
        kb = self.knowledge_base_mapper.select_by_id(kb_id)
        if kb is None:
            raise NotFoundException("知识库不存在")
        return kb
