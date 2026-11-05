from typing import Iterable, List, Optional

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import Permission


class PermissionMapper:
    """permissions 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, permission_id: int) -> Optional[Permission]:
        """按主键查询权限记录。"""
        return self.db.get(Permission, permission_id)

    def select_by_user(self, user_id: int) -> List[Permission]:
        """查询某用户的全部权限记录（含审批中/已拒绝），按申请时间倒序。"""
        stmt = select(Permission).where(Permission.user_id == user_id).order_by(Permission.applied_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def select_by_target(self, target_type: str, target_id: int) -> List[Permission]:
        """查询某个知识库/文档上的全部权限记录，按申请时间倒序。"""
        stmt = (
            select(Permission)
            .where(Permission.target_type == target_type, Permission.target_id == target_id)
            .order_by(Permission.applied_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def exists_approved(self, user_id: int, permission_type: str, target_type: str, target_id: int) -> bool:
        """判断某用户在某 target 上是否已拥有指定类型的已通过权限。"""
        stmt = select(Permission.id).where(
            Permission.user_id == user_id,
            Permission.permission_type == permission_type,
            Permission.target_type == target_type,
            Permission.target_id == target_id,
            Permission.status == "approved",
        ).limit(1)
        return self.db.execute(stmt).scalar() is not None

    def exists_approved_any(
            self, user_id: int, permission_types: Iterable[str], target_type: str, target_id: int
    ) -> bool:
        """判断某用户在某 target 上是否拥有列表中任一类型的已通过权限（用于「至少读/写/管理」的判断）。"""
        stmt = select(Permission.id).where(
            Permission.user_id == user_id,
            Permission.permission_type.in_(list(permission_types)),
            Permission.target_type == target_type,
            Permission.target_id == target_id,
            Permission.status == "approved",
        ).limit(1)
        return self.db.execute(stmt).scalar() is not None

    def select_user_ids_with_approved(self, permission_type: str, target_type: str, target_id: int) -> List[int]:
        """查询在某 target 上已拥有指定类型已通过权限的全部用户 id（如找出该知识库的全部管理员）。"""
        stmt = select(Permission.user_id).where(
            Permission.permission_type == permission_type,
            Permission.target_type == target_type,
            Permission.target_id == target_id,
            Permission.status == "approved",
        ).distinct()
        return list(self.db.execute(stmt).scalars().all())

    def exists_pending(self, user_id: int, target_type: str, target_id: int) -> bool:
        """判断某用户在某 target 上是否已有一条审批中的申请。"""
        stmt = select(Permission.id).where(
            Permission.user_id == user_id,
            Permission.target_type == target_type,
            Permission.target_id == target_id,
            Permission.status == "pending",
        ).limit(1)
        return self.db.execute(stmt).scalar() is not None

    def insert(self, permission: Permission) -> None:
        """新增权限记录，flush 后 permission.id 即可用。"""
        self.db.add(permission)
        self.db.flush()

    def delete(self, permission: Permission) -> None:
        """删除一条权限记录（撤回申请 / 撤销授权）。"""
        self.db.delete(permission)

    def select_approved_ids(
            self, user_id: int, permission_types: Iterable[str], target_type: str, target_id: int
    ) -> List[int]:
        """查询某用户在某 target 上指定类型的已通过权限记录 id（获得更高权限后定位要清理的冗余低权限记录）。"""
        stmt = select(Permission.id).where(
            Permission.user_id == user_id,
            Permission.permission_type.in_(list(permission_types)),
            Permission.target_type == target_type,
            Permission.target_id == target_id,
            Permission.status == "approved",
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_by_ids(self, permission_ids: Iterable[int]) -> None:
        """按 id 批量删除权限记录。"""
        ids = list(permission_ids)
        if ids:
            self.db.execute(delete(Permission).where(Permission.id.in_(ids)))
