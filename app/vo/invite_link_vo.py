from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .user_vo import UserBriefVO


class InviteLinkVO(BaseModel):
    """邀请链接信息；permission_id 非空表示已被兑换，绑定的是兑换时生成的那条权限记录。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    target_type: str
    target_id: int
    permission_type: str
    permission_id: Optional[int]
    is_revoked: bool
    expires_at: Optional[datetime]
    created_at: datetime
    redeemed_by: Optional[UserBriefVO] = None
    redeemed_at: Optional[datetime] = None


class InviteLinkRedeemResultVO(BaseModel):
    """使用邀请链接后的结果，供前端跳转到对应的知识库/文档。"""
    target_type: str
    target_id: int
    permission_type: str
