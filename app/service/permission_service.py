from datetime import datetime
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import ConflictException, ForbiddenException, NotFoundException
from ..config.database import get_db
from ..dto.permission_dto import PermissionApplyDTO, PermissionInviteDTO
from ..entity import Permission, User
from ..mapper.document_mapper import DocumentMapper
from ..mapper.permission_mapper import PermissionMapper
from ..mapper.user_mapper import UserMapper
from ..service.access_control import AccessControl
from ..service.knowledge_base_service import KnowledgeBaseService
from ..service.notification_service import NotificationService
from ..vo.permission_vo import AccessLevelVO, PermissionVO
from ..vo.user_vo import UserBriefVO


class PermissionService:
    """权限申请 / 邀请 / 审批相关业务；实际的访问拦截见 AccessControl，由 Document/KnowledgeBaseService 调用。"""

    def __init__(
        self,
        db: Session = Depends(get_db),
        permission_mapper: PermissionMapper = Depends(),
        user_mapper: UserMapper = Depends(),
        document_mapper: DocumentMapper = Depends(),
        knowledge_base_service: KnowledgeBaseService = Depends(),
        access_control: AccessControl = Depends(),
        notification_service: NotificationService = Depends(),
    ):
        """构造器注入数据库会话及各 Mapper / Service。"""
        self.db = db
        self.permission_mapper = permission_mapper
        self.user_mapper = user_mapper
        self.document_mapper = document_mapper
        self.knowledge_base_service = knowledge_base_service
        self.access_control = access_control
        self.notification_service = notification_service

    # ========================= 查询 =========================

    def list_mine(self, current: User) -> List[PermissionVO]:
        """查看我发起的全部权限记录（自助申请 + 被邀请）。"""
        return [self._to_vo(p) for p in self.permission_mapper.select_by_user(current.id)]

    def my_access(self, target_type: str, target_id: int, current: User) -> AccessLevelVO:
        """查询当前用户对某 target 的有效权限（读/写/管理各自是否满足），供前端决定按钮显隐。"""
        self._check_target_exists(target_type, target_id)
        knowledge_base_id = self._resolve_knowledge_base_id(target_type, target_id)
        return AccessLevelVO(
            read=self.access_control.has_access(current, "read", target_type, target_id, knowledge_base_id),
            write=self.access_control.has_access(current, "write", target_type, target_id, knowledge_base_id),
            admin=self.access_control.has_access(current, "admin", target_type, target_id, knowledge_base_id),
        )

    def list_for_target(self, target_type: str, target_id: int, current: User) -> List[PermissionVO]:
        """查看某个知识库/文档上的全部权限记录；仅对该 target 有管理权限的人（或系统管理员）可见。

        不包含当前查看者自己的记录——不管是创建知识库时自动获得的管理权限，
        还是自己申请/被邀请的记录，对管理者自己而言都没有"审批信息"可看的意义。
        """
        self._check_target_exists(target_type, target_id)
        if not self._can_manage(current, target_type, target_id):
            raise ForbiddenException("只有该知识库/文档的管理权限持有者才能查看权限列表")
        return [
            self._to_vo(p) for p in self.permission_mapper.select_by_target(target_type, target_id)
            if p.user_id != current.id
        ]

    # ========================= 写操作 =========================

    def apply(self, dto: PermissionApplyDTO, current: User) -> PermissionVO:
        """自助申请权限，提交后状态为「审批中」，等待该 target 的管理权限持有者审批。"""
        self._check_target_exists(dto.target_type, dto.target_id)
        if self.permission_mapper.exists_approved(current.id, dto.permission_type, dto.target_type, dto.target_id):
            raise ConflictException("已拥有该权限")
        if self.permission_mapper.exists_pending(current.id, dto.target_type, dto.target_id):
            raise ConflictException("已有一条待审批的申请，请勿重复提交")

        permission = Permission(
            user_id=current.id,
            permission_type=dto.permission_type,
            target_type=dto.target_type,
            target_id=dto.target_id,
            status="pending",
            applied_at=datetime.now(),
        )
        self.permission_mapper.insert(permission)

        knowledge_base_id = self._resolve_knowledge_base_id(dto.target_type, dto.target_id)
        approver_ids = self._approver_ids(dto.target_type, dto.target_id, knowledge_base_id)
        self.notification_service.notify_permission_applied(permission, current, approver_ids)

        self.db.commit()
        return self._to_vo(permission)

    def invite(self, dto: PermissionInviteDTO, current: User) -> PermissionVO:
        """直接邀请某用户获得权限，发起人须已对该 target 拥有管理权限；提交后直接「已通过」。"""
        self._check_target_exists(dto.target_type, dto.target_id)
        if not self._can_manage(current, dto.target_type, dto.target_id):
            raise ForbiddenException("只有该知识库/文档的管理权限持有者才能邀请他人")
        invitee = self.user_mapper.select_by_username(dto.username)
        if invitee is None:
            raise NotFoundException("被邀请的用户不存在")
        if self.permission_mapper.exists_approved(invitee.id, dto.permission_type, dto.target_type, dto.target_id):
            raise ConflictException("该用户已拥有该权限")

        now = datetime.now()
        permission = Permission(
            user_id=invitee.id,
            permission_type=dto.permission_type,
            target_type=dto.target_type,
            target_id=dto.target_id,
            status="approved",
            applied_at=now,
            approved_at=now,
            inviter_id=current.id,
        )
        self.permission_mapper.insert(permission)

        knowledge_base_id = self._resolve_knowledge_base_id(dto.target_type, dto.target_id)
        self.access_control.ensure_knowledge_base_baseline(invitee.id, dto.target_type, dto.target_id, knowledge_base_id)
        self.access_control.prune_lower(invitee.id, dto.permission_type, dto.target_type, dto.target_id)

        self.db.commit()
        return self._to_vo(permission)

    def review(self, permission_id: int, approve: bool, current: User) -> PermissionVO:
        """审批一条「审批中」的申请；通过后把审批人记为邀请人。"""
        permission = self._get_pending(permission_id)
        if not self._can_manage(current, permission.target_type, permission.target_id):
            raise ForbiddenException("只有该知识库/文档的管理权限持有者才能审批")

        permission.status = "approved" if approve else "rejected"
        permission.approved_at = datetime.now()
        if approve:
            permission.inviter_id = current.id
            knowledge_base_id = self._resolve_knowledge_base_id(permission.target_type, permission.target_id)
            self.access_control.ensure_knowledge_base_baseline(
                permission.user_id, permission.target_type, permission.target_id, knowledge_base_id
            )
            self.access_control.prune_lower(
                permission.user_id, permission.permission_type, permission.target_type, permission.target_id
            )
        self.notification_service.mark_read_by_permission(permission.id)
        self.db.commit()
        return self._to_vo(permission)

    def delete(self, permission_id: int, current: User) -> None:
        """撤回自己审批中的申请，或由管理权限持有者撤销一条权限记录。"""
        permission = self.permission_mapper.select_by_id(permission_id)
        if permission is None:
            raise NotFoundException("权限记录不存在")

        is_owner_withdrawing_pending = permission.user_id == current.id and permission.status == "pending"
        if not is_owner_withdrawing_pending and not self._can_manage(current, permission.target_type, permission.target_id):
            raise ForbiddenException("无权删除该权限记录")

        self.permission_mapper.delete(permission)
        self.db.commit()

    # ========================= 私有方法 =========================

    def _get_pending(self, permission_id: int) -> Permission:
        """按 id 获取一条「审批中」的权限记录，不存在或状态不对时报错。"""
        permission = self.permission_mapper.select_by_id(permission_id)
        if permission is None:
            raise NotFoundException("权限记录不存在")
        if permission.status != "pending":
            raise ConflictException("该申请已被处理，无法重复审批")
        return permission

    def _can_manage(self, current: User, target_type: str, target_id: int) -> bool:
        """判断当前用户是否可以审批/邀请/管理某 target 的权限：系统管理员，或已拥有该 target 的「管理权限」
        （文档的管理权限可继承自所属知识库）。"""
        knowledge_base_id = self._resolve_knowledge_base_id(target_type, target_id)
        return self.access_control.has_access(current, "admin", target_type, target_id, knowledge_base_id)

    def _approver_ids(self, target_type: str, target_id: int, knowledge_base_id: Optional[int]) -> set:
        """汇总所有能审批某 target 的用户 id：系统管理员 + 该 target 的管理权限持有者（文档还要算上所属知识库的）。"""
        ids = set(self.user_mapper.select_admin_ids())
        ids |= set(self.permission_mapper.select_user_ids_with_approved("admin", target_type, target_id))
        if target_type == "document" and knowledge_base_id is not None:
            ids |= set(self.permission_mapper.select_user_ids_with_approved("admin", "knowledge_base", knowledge_base_id))
        return ids

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

    def _to_vo(self, permission: Permission) -> PermissionVO:
        """将权限实体转换为 VO，并补充申请人/邀请人的简要信息。"""
        vo = PermissionVO.model_validate(permission)
        ids = {permission.user_id} | ({permission.inviter_id} if permission.inviter_id else set())
        users = {u.id: u for u in self.user_mapper.select_by_ids(ids)}
        if permission.user_id in users:
            vo.user = UserBriefVO.model_validate(users[permission.user_id])
        if permission.inviter_id in users:
            vo.inviter = UserBriefVO.model_validate(users[permission.inviter_id])
        return vo
