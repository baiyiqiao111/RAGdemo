from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import BadRequestException, ForbiddenException, NotFoundException
from ..config.database import get_db
from ..dto.invite_link_dto import InviteLinkCreateDTO
from ..entity import InviteLink, Permission, User
from ..mapper.document_mapper import DocumentMapper
from ..mapper.invite_link_mapper import InviteLinkMapper
from ..mapper.permission_mapper import PermissionMapper
from ..mapper.user_mapper import UserMapper
from ..service.access_control import AccessControl
from ..service.knowledge_base_service import KnowledgeBaseService
from ..vo.invite_link_vo import InviteLinkRedeemResultVO, InviteLinkVO
from ..vo.user_vo import UserBriefVO


class InviteLinkService:
    """邀请链接：生成分享链接，供单个用户点开自动获得指定权限，兑换一次后即失效。"""

    def __init__(
        self,
        db: Session = Depends(get_db),
        invite_link_mapper: InviteLinkMapper = Depends(),
        permission_mapper: PermissionMapper = Depends(),
        user_mapper: UserMapper = Depends(),
        document_mapper: DocumentMapper = Depends(),
        knowledge_base_service: KnowledgeBaseService = Depends(),
        access_control: AccessControl = Depends(),
    ):
        """构造器注入数据库会话（用于提交事务）及各 Mapper / Service。"""
        self.db = db
        self.invite_link_mapper = invite_link_mapper
        self.permission_mapper = permission_mapper
        self.user_mapper = user_mapper
        self.document_mapper = document_mapper
        self.knowledge_base_service = knowledge_base_service
        self.access_control = access_control

    def list_for_target(self, target_type: str, target_id: int, current: User) -> List[InviteLinkVO]:
        """查看某个知识库/文档上生成过的全部邀请链接；仅该 target 的管理权限持有者可见。"""
        self._check_target_exists(target_type, target_id)
        self._require_manage(current, target_type, target_id)
        return [self._to_vo(l) for l in self.invite_link_mapper.select_by_target(target_type, target_id)]

    def create(self, dto: InviteLinkCreateDTO, current: User) -> InviteLinkVO:
        """生成一个邀请链接；发起人须已对该 target 拥有管理权限；链接仅能被兑换一次。"""
        self._check_target_exists(dto.target_type, dto.target_id)
        self._require_manage(current, dto.target_type, dto.target_id)

        link = InviteLink(
            token=InviteLinkMapper.generate_token(),
            target_type=dto.target_type,
            target_id=dto.target_id,
            permission_type=dto.permission_type,
            created_by=current.id,
            expires_at=datetime.now() + timedelta(hours=dto.expires_in_hours) if dto.expires_in_hours else None,
        )
        self.invite_link_mapper.insert(link)
        self.db.commit()
        return self._to_vo(link)

    def revoke(self, link_id: int, current: User) -> None:
        """撤销一条邀请链接；创建者本人或该 target 的管理权限持有者均可操作。"""
        link = self.invite_link_mapper.select_by_id(link_id)
        if link is None:
            raise NotFoundException("邀请链接不存在")
        if link.created_by != current.id and not self._can_manage(current, link.target_type, link.target_id):
            raise ForbiddenException("无权撤销该邀请链接")
        link.is_revoked = True
        self.db.commit()

    def redeem(self, token: str, current: User) -> InviteLinkRedeemResultVO:
        """使用邀请链接：校验有效性后立即授予对应权限，并把生成的权限记录绑定到该链接；每条链接只能被兑换一次。"""
        link = self.invite_link_mapper.select_by_token(token)
        if link is None:
            raise NotFoundException("邀请链接不存在或已失效")
        if link.is_revoked:
            raise BadRequestException("该邀请链接已被撤销")
        if link.permission_id is not None:
            raise BadRequestException("该邀请链接已被使用")
        if link.expires_at is not None and link.expires_at < datetime.now():
            raise BadRequestException("该邀请链接已过期")
        self._check_target_exists(link.target_type, link.target_id)
        knowledge_base_id = self._resolve_knowledge_base_id(link.target_type, link.target_id)

        now = datetime.now()
        permission = Permission(
            user_id=current.id,
            permission_type=link.permission_type,
            target_type=link.target_type,
            target_id=link.target_id,
            status="approved",
            applied_at=now,
            approved_at=now,
            inviter_id=link.created_by,
        )
        self.permission_mapper.insert(permission)
        link.permission_id = permission.id
        self.access_control.ensure_knowledge_base_baseline(current.id, link.target_type, link.target_id, knowledge_base_id)
        self.access_control.prune_lower(current.id, link.permission_type, link.target_type, link.target_id)

        self.db.commit()
        return InviteLinkRedeemResultVO(
            target_type=link.target_type, target_id=link.target_id, permission_type=link.permission_type,
        )

    # ========================= 私有方法 =========================

    def _can_manage(self, current: User, target_type: str, target_id: int) -> bool:
        """判断当前用户是否可以生成/撤销某 target 的邀请链接：系统管理员，或已拥有该 target 的「管理权限」。"""
        knowledge_base_id = self._resolve_knowledge_base_id(target_type, target_id)
        return self.access_control.has_access(current, "admin", target_type, target_id, knowledge_base_id)

    def _require_manage(self, current: User, target_type: str, target_id: int) -> None:
        if not self._can_manage(current, target_type, target_id):
            raise ForbiddenException("只有该知识库/文档的管理权限持有者才能生成邀请链接")

    def _resolve_knowledge_base_id(self, target_type: str, target_id: int) -> Optional[int]:
        """返回用于权限继承判断的知识库 id；target 本身是知识库时直接返回自身 id。"""
        if target_type == "knowledge_base":
            return target_id
        doc = self.document_mapper.select_by_id(target_id)
        return doc.knowledge_base_id if doc else None

    def _check_target_exists(self, target_type: str, target_id: int) -> None:
        """校验知识库/文档存在且未删除。"""
        if target_type == "knowledge_base":
            self.knowledge_base_service.get_alive(target_id)
        else:
            doc = self.document_mapper.select_by_id(target_id)
            if doc is None or doc.is_deleted:
                raise NotFoundException("文档不存在")

    def _to_vo(self, link: InviteLink) -> InviteLinkVO:
        """将邀请链接转换为 VO；已被兑换时补充兑换人和兑换时间（取自绑定的权限记录）。"""
        vo = InviteLinkVO.model_validate(link)
        if link.permission_id is not None:
            permission = self.permission_mapper.select_by_id(link.permission_id)
            if permission is not None:
                vo.redeemed_at = permission.approved_at
                user = self.user_mapper.select_by_id(permission.user_id)
                if user is not None:
                    vo.redeemed_by = UserBriefVO.model_validate(user)
        return vo
