from typing import List

from fastapi import APIRouter, Depends, Query, Response, status

from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.notification_service import NotificationService
from ..vo.notification_vo import NotificationVO

router = APIRouter(prefix="/api/notifications", tags=["通知"])


@router.get("", response_model=List[NotificationVO])
def list_notifications(
    unread_only: bool = Query(default=False, description="只看未读"),
    notification_service: NotificationService = Depends(),
    current: User = Depends(get_current_user),
):
    """查看我的通知，按创建时间倒序。"""
    return notification_service.list_mine(current, unread_only)


@router.get("/unread-count")
def unread_count(notification_service: NotificationService = Depends(), current: User = Depends(get_current_user)):
    """统计我的未读通知数，供前端小红点使用。"""
    return {"count": notification_service.unread_count(current)}


@router.post("/{notification_id}/read", response_model=NotificationVO)
def mark_read(
    notification_id: int,
    notification_service: NotificationService = Depends(),
    current: User = Depends(get_current_user),
):
    """把一条通知标记为已读。"""
    return notification_service.mark_read(notification_id, current)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(notification_service: NotificationService = Depends(), current: User = Depends(get_current_user)):
    """把我的全部通知标记为已读。"""
    notification_service.mark_all_read(current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
