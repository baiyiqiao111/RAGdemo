from typing import Optional

from pydantic import BaseModel, Field


class DocumentCreateDTO(BaseModel):
    """新建文档请求体；文档不能脱离知识库独立存在，必须指定所属知识库。"""
    title: str = Field(min_length=1, max_length=255)
    content: str = ""
    knowledge_base_id: int
    parent_id: Optional[int] = None
    sort_order: int = 0


class DocumentUpdateDTO(BaseModel):
    """编辑文档请求体，需携带版本号用于乐观锁校验。"""
    # 所有字段可选，只更新传了的字段
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    # 客户端打开文档时拿到的版本号；与库中不一致说明别人已改过，返回 409
    version: int


class DocumentQueryDTO(BaseModel):
    """文档分页查询条件（≈ XxxQuery / PageParam）。"""
    keyword: Optional[str] = None
    knowledge_base_id: Optional[int] = None
    parent_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
