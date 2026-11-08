from typing import List, Optional

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import Notification


class NotificationMapper:
    """notifications 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, notification_id: int) -> Optional[Notification]:
        """按主键查询通知。"""
        return self.db.get(Notification, notification_id)

    def select_by_user(self, user_id: int, unread_only: bool = False) -> List[Notification]:
        """查询某用户的通知，按创建时间倒序。"""
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read.is_(False))
        stmt = select(Notification).where(*conditions).order_by(Notification.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def count_unread(self, user_id: int) -> int:
        """统计某用户的未读通知数。"""
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
        return self.db.execute(stmt).scalar_one()

    def insert_many(self, notifications: List[Notification]) -> None:
        """批量新增通知。"""
        self.db.add_all(notifications)
        self.db.flush()

    def mark_all_read(self, user_id: int) -> None:
        """把某用户的全部未读通知标记为已读。"""
        self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )

    def mark_read_by_permission(self, permission_id: int) -> None:
        """申请被审批后，把所有审批人收到的相关待办通知标记为已读（避免其他审批人看到已处理过的旧待办）。"""
        self.db.execute(
            update(Notification)
            .where(Notification.permission_id == permission_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
