from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from ..config.database import get_db
from ..dto.user_dto import UserLoginDTO, UserRegisterDTO, UserUpdateDTO
from ..entity import User
from ..mapper.user_mapper import UserMapper
from ..util.jwt_util import create_access_token
from ..util.password_util import hash_password, verify_password
from ..vo.user_vo import TokenVO, UserVO


class UserService:
    """用户相关业务：注册、登录。"""

    def __init__(self, db: Session = Depends(get_db), user_mapper: UserMapper = Depends()):
        """构造器注入数据库会话（用于提交事务）和 UserMapper。"""
        self.db = db
        self.user_mapper = user_mapper

    def register(self, dto: UserRegisterDTO) -> UserVO:
        """注册新用户；用户名或邮箱重复抛 409，第一个注册的用户自动成为管理员。"""
        if self.user_mapper.exists_by_username_or_email(dto.username, dto.email):
            raise ConflictException("用户名或邮箱已存在")

        is_first = self.user_mapper.count() == 0
        user = User(
            username=dto.username,
            password_hash=hash_password(dto.password),
            nickname=dto.nickname or dto.username,
            email=dto.email,
            role="admin" if is_first else "member",
        )
        self.user_mapper.insert(user)
        self.db.commit()
        return UserVO.model_validate(user)

    def login(self, dto: UserLoginDTO) -> TokenVO:
        """校验用户名密码，成功后更新最后登录时间并签发访问令牌。"""
        user = self.user_mapper.select_by_username(dto.username)
        if user is None or not verify_password(dto.password, user.password_hash):
            raise UnauthorizedException("用户名或密码错误")
        if not user.is_active:
            raise ForbiddenException("账号已被禁用")

        user.last_login_at = datetime.now()
        self.db.commit()
        return TokenVO(access_token=create_access_token(user.id), user=UserVO.model_validate(user))

    def update_profile(self, user: User, dto: UserUpdateDTO) -> UserVO:
        """更新当前用户的昵称 / 邮箱 / 头像；邮箱被其他账号占用时抛 409。"""
        if dto.email and self.user_mapper.exists_by_email(dto.email, user.id):
            raise ConflictException("邮箱已被占用")

        if dto.nickname is not None:
            user.nickname = dto.nickname
        if dto.email is not None:
            user.email = dto.email
        if dto.avatar_url is not None:
            user.avatar_url = dto.avatar_url
        self.db.commit()
        return UserVO.model_validate(user)
