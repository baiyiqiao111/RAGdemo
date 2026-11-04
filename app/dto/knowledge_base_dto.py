from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreateDTO(BaseModel):
    """新建知识库请求体。"""
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
