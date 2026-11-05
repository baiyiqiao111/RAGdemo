from typing import Literal

from pydantic import BaseModel

PermissionType = Literal["read", "write", "admin"]
TargetType = Literal["knowledge_base", "document"]


class PermissionApplyDTO(BaseModel):
    """自助申请权限请求体：申请人即当前登录用户，提交后状态为「审批中」。"""
    permission_type: PermissionType
    target_type: TargetType
    target_id: int


class PermissionInviteDTO(BaseModel):
    """直接邀请某用户获得权限请求体；发起人须已对该 target 拥有管理权限，提交后直接「已通过」。"""
    username: str
    permission_type: PermissionType
    target_type: TargetType
    target_id: int


class PermissionReviewDTO(BaseModel):
    """审批「审批中」申请的请求体。"""
    approve: bool
