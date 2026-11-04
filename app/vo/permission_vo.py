from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .user_vo import UserBriefVO


class PermissionVO(BaseModel):
    """权限申请 / 授权记录。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    permission_type: str
    target_type: str
    target_id: int
    status: str
    applied_at: datetime
    approved_at: Optional[datetime]
    inviter_id: Optional[int]
    user: Optional[UserBriefVO] = None
    inviter: Optional[UserBriefVO] = None
