from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import settings

# 数据源 + 连接池（≈ DataSource / HikariCP）
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 实体的声明式基类。"""


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每个请求一个数据库会话，同一请求内的 Mapper/Service 共享；未提交的修改在关闭时回滚。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
