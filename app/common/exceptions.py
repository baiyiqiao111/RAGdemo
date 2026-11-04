class BusinessException(Exception):
    """业务异常基类（≈ 自定义 RuntimeException），由全局异常处理器统一转换为 HTTP 响应。"""
    status_code = 400

    def __init__(self, message: str):
        """创建异常，message 会作为响应中的 detail 返回给前端。"""
        super().__init__(message)
        self.message = message


class BadRequestException(BusinessException):
    """请求不合法（400）。"""
    status_code = 400


class UnauthorizedException(BusinessException):
    """未登录或令牌无效（401）。"""
    status_code = 401


class ForbiddenException(BusinessException):
    """无权限操作（403）。"""
    status_code = 403


class NotFoundException(BusinessException):
    """资源不存在（404）。"""
    status_code = 404


class ConflictException(BusinessException):
    """资源冲突，如用户名重复、乐观锁版本不一致（409）。"""
    status_code = 409
