import secrets
from typing import Iterable, List, Optional

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import InviteLink


class InviteLinkMapper:
    """invite_links 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, link_id: int) -> Optional[InviteLink]:
        """按主键查询邀请链接。"""
        return self.db.get(InviteLink, link_id)

    def select_by_token(self, token: str) -> Optional[InviteLink]:
        """按 token 查询邀请链接（兑换时用）。"""
        stmt = select(InviteLink).where(InviteLink.token == token)
        return self.db.execute(stmt).scalar_one_or_none()

    def select_by_target(self, target_type: str, target_id: int) -> List[InviteLink]:
        """查询某个知识库/文档上生成过的全部邀请链接，按创建时间倒序。"""
        stmt = (
            select(InviteLink)
            .where(InviteLink.target_type == target_type, InviteLink.target_id == target_id)
            .order_by(InviteLink.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def insert(self, link: InviteLink) -> None:
        """新增邀请链接，flush 后 link.id 即可用。"""
        self.db.add(link)
        self.db.flush()

    def detach_and_revoke_by_permission_ids(self, permission_ids: Iterable[int]) -> None:
        """这些权限记录即将被删除（如被更高权限替换）：解除邀请链接对它们的引用并标记撤销。

        否则 permission_id 的外键约束会导致权限记录删不掉；链接本身的使用记录已经没有意义，一并撤销。
        """
        ids = list(permission_ids)
        if not ids:
            return
        self.db.execute(
            update(InviteLink)
            .where(InviteLink.permission_id.in_(ids))
            .values(permission_id=None, is_revoked=True)
        )

    @staticmethod
    def generate_token() -> str:
        """生成一个不可猜测的随机令牌。"""
        return secrets.token_urlsafe(24)
