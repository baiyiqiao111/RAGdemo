"""应用启动入口（≈ @SpringBootApplication 启动类）：组装配置、实体、全局异常处理和各 Controller。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import entity  # noqa: F401  导入实体，把表注册到 Base.metadata
from .common.exception_handler import register_exception_handlers
from .config.database import Base, engine
from .controller import (
    auth_controller,
    document_controller,
    file_controller,
    invite_link_controller,
    knowledge_base_controller,
    notification_controller,
    permission_controller,
    rag_controller,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# 开发阶段直接建表；正式环境建议改用 Alembic 管理迁移
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RAG 企业知识库", version="0.1.0")
register_exception_handlers(app)
app.include_router(auth_controller.router)
app.include_router(knowledge_base_controller.router)
app.include_router(document_controller.router)
app.include_router(file_controller.router)
app.include_router(permission_controller.router)
app.include_router(notification_controller.router)
app.include_router(invite_link_controller.router)
app.include_router(rag_controller.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    """返回前端单页应用的入口页面。"""
    return FileResponse(STATIC_DIR / "index.html")
