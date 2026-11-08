from typing import Iterable, List

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import NotFoundException
from ..config.database import get_db
from ..entity import Notification, Permission, User
from ..mapper.notification_mapper import NotificationMapper
from ..vo.notification_vo import NotificationVO


class NotificationService:
    """系统通知相关业务：目前只服务于权限申请的待办提醒。"""

    def __init__(self, db: Session = Depends(get_db), notification_mapper: NotificationMapper = Depends()):
        """构造器注入数据库会话（用于提交事务）和 NotificationMapper。"""
        self.db = db
        self.notification_mapper = notification_mapper

    def list_mine(self, current: User, unread_only: bool = False) -> List[NotificationVO]:
        """查看我的通知，按创建时间倒序。"""
        return [
            NotificationVO.model_validate(n)
            for n in self.notification_mapper.select_by_user(current.id, unread_only)
        ]

    def unread_count(self, current: User) -> int:
        """统计我的未读通知数，供前端小红点使用。"""
        return self.notification_mapper.count_unread(current.id)

    def mark_read(self, notification_id: int, current: User) -> NotificationVO:
        """把一条通知标记为已读（点进去查看详情/审批时调用）。"""
        notification = self.notification_mapper.select_by_id(notification_id)
        if notification is None or notification.user_id != current.id:
            raise NotFoundException("通知不存在")
        if not notification.is_read:
            notification.is_read = True
            self.db.commit()
        return NotificationVO.model_validate(notification)

    def mark_all_read(self, current: User) -> None:
        """把我的全部通知标记为已读。"""
        self.notification_mapper.mark_all_read(current.id)
        self.db.commit()

    def mark_read_by_permission(self, permission_id: int) -> None:
        """申请被审批后清掉所有审批人的相关待办（不单独提交事务，由调用方一起提交）。"""
        self.notification_mapper.mark_read_by_permission(permission_id)

    def notify_permission_applied(self, permission: Permission, applicant: User, approver_ids: Iterable[int]) -> None:
        """权限申请提交时，给所有能审批该 target 的人创建一条待办通知（不单独提交事务，由调用方一起提交）。"""
        type_label = {"read": "读权限", "write": "写权限", "admin": "管理权限"}[permission.permission_type]
        target_label = "知识库" if permission.target_type == "knowledge_base" else "文档"
        title = f"{applicant.nickname} 申请了 {target_label} #{permission.target_id} 的{type_label}"

        notifications = [
            Notification(
                user_id=user_id,
                permission_id=permission.id,
                target_type=permission.target_type,
                target_id=permission.target_id,
                title=title,
                content="待审批，点击查看并处理",
            )
            for user_id in set(approver_ids) - {applicant.id}
        ]
        if notifications:
            self.notification_mapper.insert_many(notifications)
