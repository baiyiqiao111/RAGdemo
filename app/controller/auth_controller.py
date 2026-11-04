from fastapi import APIRouter, Depends, status

from ..dto.user_dto import UserLoginDTO, UserRegisterDTO, UserUpdateDTO
from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.user_service import UserService
from ..vo.user_vo import TokenVO, UserVO

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserVO, status_code=status.HTTP_201_CREATED)
def register(body: UserRegisterDTO, user_service: UserService = Depends()):
    """注册新用户；用户名或邮箱重复返回 409，第一个注册的用户自动成为管理员。"""
    return user_service.register(body)


@router.post("/login", response_model=TokenVO)
def login(body: UserLoginDTO, user_service: UserService = Depends()):
    """用户名密码登录，成功后返回访问令牌。"""
    return user_service.login(body)


@router.get("/me", response_model=UserVO)
def me(current: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return UserVO.model_validate(current)


@router.put("/me", response_model=UserVO)
def update_me(
    body: UserUpdateDTO,
    current: User = Depends(get_current_user),
    user_service: UserService = Depends(),
):
    """更新当前登录用户的昵称 / 邮箱 / 头像。"""
    return user_service.update_profile(current, body)
