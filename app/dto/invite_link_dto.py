from typing import Optional

from pydantic import BaseModel, Field

from .permission_dto import PermissionType, TargetType


class InviteLinkCreateDTO(BaseModel):
    """生成邀请链接请求体，发起人须已对该 target 拥有管理权限；链接仅能被兑换一次。"""
    target_type: TargetType
    target_id: int
    permission_type: PermissionType
    expires_in_hours: Optional[int] = Field(default=None, gt=0, description="多少小时后过期，不传则永不过期")


class InviteLinkRedeemDTO(BaseModel):
    """使用邀请链接请求体。"""
    token: str
