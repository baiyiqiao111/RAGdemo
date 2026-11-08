from datetime import datetime
from typing import Optional

from fastapi import Depends

from ..common.exceptions import ForbiddenException
from ..entity import Permission, User
from ..mapper.invite_link_mapper import InviteLinkMapper
from ..mapper.permission_mapper import PermissionMapper

# 权限等级：拥有更高等级隐含拥有更低等级（admin ⊃ write ⊃ read）
_AT_LEAST = {
    "read": ("read", "write", "admin"),
    "write": ("write", "admin"),
    "admin": ("admin",),
}
_LEVEL = {"read": 1, "write": 2, "admin": 3}
_LABEL = {"read": "读权限", "write": "写权限", "admin": "管理权限"}


class AccessControl:
    """知识库 / 文档的统一权限校验。只依赖 PermissionMapper，避免与具体业务 Service 相互依赖。"""

    def __init__(self, permission_mapper: PermissionMapper = Depends(), invite_link_mapper: InviteLinkMapper = Depends()):
        """构造器注入 PermissionMapper 和 InviteLinkMapper。"""
        self.permission_mapper = permission_mapper
        self.invite_link_mapper = invite_link_mapper

    def has_access(
            self, user: User, required: str, target_type: str, target_id: int,
            knowledge_base_id: Optional[int] = None,
    ) -> bool:
        """判断用户对某 target 是否拥有 >= required 的有效权限。

        系统管理员（role=admin）直通；文档的权限还可以继承自其所属知识库的权限
        （拥有知识库的读/写/管理权限，即对库内所有文档拥有同等权限）。
        """
        if user.role == "admin":
            return True
        types = _AT_LEAST[required]
        if self.permission_mapper.exists_approved_any(user.id, types, target_type, target_id):
            return True
        if target_type == "document" and knowledge_base_id is not None:
            return self.permission_mapper.exists_approved_any(user.id, types, "knowledge_base", knowledge_base_id)
        return False

    def require_access(
            self, user: User, required: str, target_type: str, target_id: int,
            knowledge_base_id: Optional[int] = None,
    ) -> None:
        """权限不足时抛 403。"""
        if not self.has_access(user, required, target_type, target_id, knowledge_base_id):
            raise ForbiddenException(f"需要{_LABEL[required]}才能执行该操作")

    def grant(self, user_id: int, permission_type: str, target_type: str, target_id: int) -> None:
        """系统自动授权（如知识库创建者自动获得管理权限），不走审批流程，立即生效。"""
        now = datetime.now()
        permission = Permission(
            user_id=user_id,
            permission_type=permission_type,
            target_type=target_type,
            target_id=target_id,
            status="approved",
            applied_at=now,
            approved_at=now,
        )
        self.permission_mapper.insert(permission)

    def ensure_knowledge_base_baseline(
            self, user_id: int, target_type: str, target_id: int, knowledge_base_id: Optional[int],
    ) -> None:
        """文档权限授予后，确保被授权人至少拥有所属知识库的读权限。

        否则界面里看不到这个知识库、进不去目录树，拿到的文档权限也就无从导航使用。
        若已有该知识库任意级别的权限（读/写/管理）则不重复授予。
        """
        if target_type != "document" or knowledge_base_id is None:
            return
        if self.permission_mapper.exists_approved_any(user_id, _AT_LEAST["read"], "knowledge_base", knowledge_base_id):
            return
        self.grant(user_id, "read", "knowledge_base", knowledge_base_id)

    def prune_lower(self, user_id: int, permission_type: str, target_type: str, target_id: int) -> None:
        """获得更高权限后，删除同一用户在该 target 上级别更低的已通过权限记录，避免冗余。

        只精确匹配同一个 target_type + target_id，不会动知识库/文档之间互相继承来的权限。
        删除前先解除邀请链接对这些记录的引用（否则外键约束会导致删除失败），
        并把对应的邀请链接标记撤销——它们授予的权限已经被更高权限取代，不再有效。
        """
        lower_types = [t for t, level in _LEVEL.items() if level < _LEVEL[permission_type]]
        if not lower_types:
            return
        permission_ids = self.permission_mapper.select_approved_ids(user_id, lower_types, target_type, target_id)
        if not permission_ids:
            return
        self.invite_link_mapper.detach_and_revoke_by_permission_ids(permission_ids)
        self.permission_mapper.delete_by_ids(permission_ids)
