from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import BusinessException

# 常见字段校验失败时给出的中文提示，前端直接展示 detail 即可
FIELD_HINTS = {
    "username": "用户名需 3-64 位，只能包含英文字母、数字、下划线、点或短横线",
    "password": "密码需 6-72 位",
    "nickname": "昵称最多 64 个字符",
    "email": "邮箱最多 128 个字符",
    "title": "标题不能为空，最多 255 个字符",
    "version": "缺少文档版本号",
}


def business_exception_handler(request: Request, exc: BusinessException):
    """把业务异常转换为 {"detail": 提示信息} 响应（≈ @ExceptionHandler(BusinessException.class)）。"""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """把参数校验错误转成可读的中文提示，同时在 errors 中保留原始明细（≈ 处理 MethodArgumentNotValidException）。"""
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else ""
        hint = FIELD_HINTS.get(field, f"参数 {field} 不合法：{err['msg']}")
        if hint not in messages:
            messages.append(hint)
    return JSONResponse(
        status_code=422,
        content={"detail": "；".join(messages) or "请求参数有误", "errors": jsonable_encoder(exc.errors())},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """在应用上注册全局异常处理器。"""
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
