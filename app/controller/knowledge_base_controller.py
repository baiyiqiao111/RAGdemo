from typing import List

from fastapi import APIRouter, Depends, status

from ..dto.knowledge_base_dto import KnowledgeBaseCreateDTO
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.knowledge_base_service import KnowledgeBaseService
from ..vo.knowledge_base_vo import KnowledgeBaseVO

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库"])


@router.get("", response_model=List[KnowledgeBaseVO])
def list_knowledge_bases(knowledge_base_service: KnowledgeBaseService = Depends(), _: User = Depends(get_current_user)):
    """返回全部知识库，按创建时间倒序。"""
    return knowledge_base_service.list_all()


@router.post("", response_model=KnowledgeBaseVO, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    body: KnowledgeBaseCreateDTO,
    knowledge_base_service: KnowledgeBaseService = Depends(),
    _: User = Depends(get_current_user),
):
    """新建知识库。"""
    return knowledge_base_service.create(body)


@router.get("/{kb_id}", response_model=KnowledgeBaseVO)
def get_knowledge_base(
    kb_id: int,
    knowledge_base_service: KnowledgeBaseService = Depends(),
    _: User = Depends(get_current_user),
):
    """获取知识库详情。"""
    return knowledge_base_service.detail(kb_id)
