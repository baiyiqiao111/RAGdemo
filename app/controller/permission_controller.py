from typing import List

from fastapi import APIRouter, Depends, Query, Response, status

from ..dto.permission_dto import PermissionApplyDTO, PermissionInviteDTO, PermissionReviewDTO, TargetType
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.permission_service import PermissionService
from ..vo.permission_vo import PermissionVO

router = APIRouter(prefix="/api/permissions", tags=["权限"])


@router.get("/mine", response_model=List[PermissionVO])
def list_my_permissions(permission_service: PermissionService = Depends(), current: User = Depends(get_current_user)):
    """查看我发起的全部权限记录（自助申请 + 被邀请）。"""
    return permission_service.list_mine(current)


@router.get("", response_model=List[PermissionVO])
def list_target_permissions(
    target_type: TargetType = Query(description="knowledge_base / document"),
    target_id: int = Query(),
    permission_service: PermissionService = Depends(),
    current: User = Depends(get_current_user),
):
    """查看某个知识库/文档上的全部权限记录；仅该 target 的管理权限持有者可见。"""
    return permission_service.list_for_target(target_type, target_id, current)


@router.post("/apply", response_model=PermissionVO, status_code=status.HTTP_201_CREATED)
def apply_permission(
    body: PermissionApplyDTO,
    permission_service: PermissionService = Depends(),
    current: User = Depends(get_current_user),
):
    """自助申请权限，提交后状态为「审批中」。"""
    return permission_service.apply(body, current)


@router.post("/invite", response_model=PermissionVO, status_code=status.HTTP_201_CREATED)
def invite_permission(
    body: PermissionInviteDTO,
    permission_service: PermissionService = Depends(),
    current: User = Depends(get_current_user),
):
    """直接邀请某用户获得权限，发起人须已拥有该 target 的管理权限；提交后直接「已通过」。"""
    return permission_service.invite(body, current)


@router.post("/{permission_id}/review", response_model=PermissionVO)
def review_permission(
    permission_id: int,
    body: PermissionReviewDTO,
    permission_service: PermissionService = Depends(),
    current: User = Depends(get_current_user),
):
    """审批一条「审批中」的申请。"""
    return permission_service.review(permission_id, body.approve, current)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    permission_service: PermissionService = Depends(),
    current: User = Depends(get_current_user),
):
    """撤回自己审批中的申请，或由管理权限持有者撤销一条权限记录。"""
    permission_service.delete(permission_id, current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
