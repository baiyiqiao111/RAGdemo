from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from ..dto.knowledge_base_dto import KnowledgeBaseCreateDTO
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.knowledge_base_service import KnowledgeBaseService
from ..vo.knowledge_base_vo import KnowledgeBaseVO

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库"])


@router.get("", response_model=List[KnowledgeBaseVO])
def list_knowledge_bases(
    knowledge_base_service: KnowledgeBaseService = Depends(),
    current: User = Depends(get_current_user),
):
    """返回当前用户有读权限的知识库，按创建时间倒序；系统管理员可看到全部。"""
    return knowledge_base_service.list_all(current)


@router.post("", response_model=KnowledgeBaseVO, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    body: KnowledgeBaseCreateDTO,
    knowledge_base_service: KnowledgeBaseService = Depends(),
    current: User = Depends(get_current_user),
):
    """新建知识库，创建者自动获得管理权限。"""
    return knowledge_base_service.create(body, current)


@router.get("/{kb_id}", response_model=KnowledgeBaseVO)
def get_knowledge_base(
    kb_id: int,
    knowledge_base_service: KnowledgeBaseService = Depends(),
    current: User = Depends(get_current_user),
):
    """获取知识库详情，需要读权限。"""
    return knowledge_base_service.detail(kb_id, current)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int,
    background_tasks: BackgroundTasks,
    knowledge_base_service: KnowledgeBaseService = Depends(),
    current: User = Depends(get_current_user),
):
    """软删除知识库，连带库内所有文档一并软删除，需要管理权限；库内全部切片异步清理。"""
    knowledge_base_service.delete(kb_id, current, background_tasks)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
