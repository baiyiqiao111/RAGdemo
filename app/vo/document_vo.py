from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .user_vo import UserBriefVO


class DocumentBriefVO(BaseModel):
    """列表/目录树用，不含正文。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    title: str
    parent_id: Optional[int]
    sort_order: int
    word_count: int
    version: int
    creator_id: int
    updater_id: int
    created_at: datetime
    updated_at: datetime


class DocumentVO(DocumentBriefVO):
    """文档详情，包含正文及创建人/编辑人信息。"""
    content: str
    content_format: str
    creator: Optional[UserBriefVO] = None
    updater: Optional[UserBriefVO] = None
