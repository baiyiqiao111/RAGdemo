from typing import List

from fastapi import APIRouter, Depends, Query, Response, status

from ..dto.invite_link_dto import InviteLinkCreateDTO, InviteLinkRedeemDTO
from ..dto.permission_dto import TargetType
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.invite_link_service import InviteLinkService
from ..vo.invite_link_vo import InviteLinkRedeemResultVO, InviteLinkVO

router = APIRouter(prefix="/api/invite-links", tags=["邀请链接"])


@router.get("", response_model=List[InviteLinkVO])
def list_invite_links(
    target_type: TargetType = Query(description="knowledge_base / document"),
    target_id: int = Query(),
    invite_link_service: InviteLinkService = Depends(),
    current: User = Depends(get_current_user),
):
    """查看某知识库/文档上生成过的邀请链接，仅管理权限持有者可见。"""
    return invite_link_service.list_for_target(target_type, target_id, current)


@router.post("", response_model=InviteLinkVO, status_code=status.HTTP_201_CREATED)
def create_invite_link(
    body: InviteLinkCreateDTO,
    invite_link_service: InviteLinkService = Depends(),
    current: User = Depends(get_current_user),
):
    """生成一个邀请链接，任何登录用户点开后自动获得指定权限。"""
    return invite_link_service.create(body, current)


@router.post("/redeem", response_model=InviteLinkRedeemResultVO)
def redeem_invite_link(
    body: InviteLinkRedeemDTO,
    invite_link_service: InviteLinkService = Depends(),
    current: User = Depends(get_current_user),
):
    """使用邀请链接的 token，立即获得其对应的知识库/文档权限。"""
    return invite_link_service.redeem(body.token, current)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite_link(
    link_id: int,
    invite_link_service: InviteLinkService = Depends(),
    current: User = Depends(get_current_user),
):
    """撤销一条邀请链接。"""
    invite_link_service.revoke(link_id, current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
