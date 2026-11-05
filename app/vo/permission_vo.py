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


class AccessLevelVO(BaseModel):
    """当前用户对某 target 的有效权限（供前端判断按钮的显示/隐藏）。"""
    read: bool
    write: bool
    admin: bool
