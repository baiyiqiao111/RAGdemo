from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationVO(BaseModel):
    """系统通知。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    permission_id: Optional[int]
    target_type: Optional[str]
    target_id: Optional[int]
    title: str
    content: Optional[str]
    is_read: bool
    created_at: datetime
