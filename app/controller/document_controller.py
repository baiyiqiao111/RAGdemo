from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status

from ..dto.document_dto import DocumentCreateDTO, DocumentQueryDTO, DocumentUpdateDTO
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.document_service import DocumentService
from ..vo.document_vo import DocumentBriefVO, DocumentVO
from ..vo.page_vo import PageVO

router = APIRouter(prefix="/api/documents", tags=["文档"])


@router.get("/tree", response_model=List[DocumentBriefVO])
def document_tree(
    knowledge_base_id: int = Query(description="知识库 id，文档不能脱离知识库独立存在"),
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """返回某知识库下全部文档（不含正文），前端按 parent_id 组装目录树；需要该知识库的读权限。"""
    return document_service.tree(knowledge_base_id, current)


@router.get("", response_model=PageVO[DocumentBriefVO])
def list_documents(
    keyword: Optional[str] = Query(default=None, description="按标题模糊搜索"),
    knowledge_base_id: Optional[int] = Query(default=None, description="只看某个知识库下的文档"),
    parent_id: Optional[int] = Query(default=None, description="只看某个文档的直接子文档"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """分页查询文档列表，支持按标题关键字、知识库、父文档过滤，按更新时间倒序；指定知识库时需要该库的读权限。"""
    query = DocumentQueryDTO(keyword=keyword, knowledge_base_id=knowledge_base_id, parent_id=parent_id, page=page, size=size)
    return document_service.page(query, current)


@router.post("", response_model=DocumentVO, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentCreateDTO,
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """新建文档，当前用户同时作为创建人和最后编辑人。"""
    return document_service.create(body, current)


@router.get("/{doc_id}", response_model=DocumentVO)
def get_document(
    doc_id: int,
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """获取单个文档详情（含正文），需要读权限。"""
    return document_service.detail(doc_id, current)


@router.put("/{doc_id}", response_model=DocumentVO)
def update_document(
    doc_id: int,
    body: DocumentUpdateDTO,
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """编辑文档，只更新传入的字段；版本号不一致返回 409。"""
    return document_service.update(doc_id, body, current)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: int,
    document_service: DocumentService = Depends(),
    current: User = Depends(get_current_user),
):
    """软删除文档及其全部子文档，需要管理权限。"""
    document_service.delete(doc_id, current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
