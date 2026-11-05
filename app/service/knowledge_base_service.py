from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import NotFoundException
from ..config.database import get_db
from ..dto.knowledge_base_dto import KnowledgeBaseCreateDTO
from ..entity import KnowledgeBase, User
from ..mapper.knowledge_base_mapper import KnowledgeBaseMapper
from ..service.access_control import AccessControl
from ..vo.knowledge_base_vo import KnowledgeBaseVO


class KnowledgeBaseService:
    """知识库相关业务：文档的顶层归属容器。"""

    def __init__(
        self,
        db: Session = Depends(get_db),
        knowledge_base_mapper: KnowledgeBaseMapper = Depends(),
        access_control: AccessControl = Depends(),
    ):
        """构造器注入数据库会话（用于提交事务）、KnowledgeBaseMapper 和 AccessControl。"""
        self.db = db
        self.knowledge_base_mapper = knowledge_base_mapper
        self.access_control = access_control

    def list_all(self, current: User) -> List[KnowledgeBaseVO]:
        """返回当前用户有读权限的知识库，按创建时间倒序；系统管理员可看到全部。"""
        kbs = self.knowledge_base_mapper.select_all()
        if current.role != "admin":
            kbs = [kb for kb in kbs if self.access_control.has_access(current, "read", "knowledge_base", kb.id)]
        return [KnowledgeBaseVO.model_validate(kb) for kb in kbs]

    def create(self, dto: KnowledgeBaseCreateDTO, current: User) -> KnowledgeBaseVO:
        """新建知识库；创建者自动获得该知识库的管理权限（无需审批），否则谁都进不了自己建的库。"""
        kb = KnowledgeBase(title=dto.title, description=dto.description)
        self.knowledge_base_mapper.insert(kb)
        self.access_control.grant(current.id, "admin", "knowledge_base", kb.id)
        self.db.commit()
        return KnowledgeBaseVO.model_validate(kb)

    def detail(self, kb_id: int, current: User) -> KnowledgeBaseVO:
        """获取知识库详情，需要读权限，不存在抛 404。"""
        kb = self.get_alive(kb_id)
        self.access_control.require_access(current, "read", "knowledge_base", kb_id)
        return KnowledgeBaseVO.model_validate(kb)

    def get_alive(self, kb_id: int) -> KnowledgeBase:
        """按 id 获取知识库实体，不存在抛 404；仅做存在性校验，不含权限判断。"""
        kb = self.knowledge_base_mapper.select_by_id(kb_id)
        if kb is None:
            raise NotFoundException("知识库不存在")
        return kb
