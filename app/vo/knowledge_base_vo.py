from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseVO(BaseModel):
    """知识库信息。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    created_at: datetime
