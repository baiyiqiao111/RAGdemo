from typing import Iterable, List, Optional

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..entity import User


class UserMapper:
    """users 表的数据访问对象。"""

    def __init__(self, db: Session = Depends(get_db)):
        """注入当前请求的数据库会话（≈ 构造器注入 SqlSession）。"""
        self.db = db

    def select_by_id(self, user_id: int) -> Optional[User]:
        """按主键查询用户。"""
        return self.db.get(User, user_id)

    def select_by_username(self, username: str) -> Optional[User]:
        """按登录名查询用户。"""
        stmt = select(User).where(User.username == username)
        return self.db.execute(stmt).scalar_one_or_none()

    def select_by_ids(self, ids: Iterable[int]) -> List[User]:
        """按主键批量查询用户。"""
        stmt = select(User).where(User.id.in_(set(ids)))
        return list(self.db.execute(stmt).scalars().all())

    def exists_by_username_or_email(
            self, username: str, email: Optional[str]
    ) -> bool:
        """判断用户名或邮箱（传了才判断）是否已被占用。"""
        conditions = [User.username == username]
        if email:
            conditions.append(User.email == email)

        stmt = select(User.id).where(or_(*conditions)).limit(1)
        return self.db.execute(stmt).scalar() is not None

    def exists_by_email(self, email: str, exclude_user_id: int) -> bool:
        """判断邮箱是否已被其他用户占用。"""
        stmt = select(User.id).where(User.email == email, User.id != exclude_user_id).limit(1)
        return self.db.execute(stmt).scalar() is not None

    def select_admin_ids(self) -> List[int]:
        """查询全部系统管理员的 id（role=admin），他们可以审批任意知识库/文档的权限申请。"""
        stmt = select(User.id).where(User.role == "admin")
        return list(self.db.execute(stmt).scalars().all())

    def count(self) -> int:
        """统计用户总数。"""
        stmt = select(func.count(User.id))
        return self.db.execute(stmt).scalar_one()

    def insert(self, user: User) -> None:
        """新增用户，flush 后 user.id 即可用。"""
        self.db.add(user)
        self.db.flush()
