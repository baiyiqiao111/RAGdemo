import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """应用配置，均可通过环境变量覆盖；frozen 保证运行期不被修改（≈ @ConfigurationProperties）。"""
    # 默认本地 MySQL；可通过环境变量 KB_DATABASE_URL 覆盖（如 sqlite:///./rag_kb.db）
    database_url: str = os.getenv(
        "KB_DATABASE_URL", "mysql+pymysql://root:root@127.0.0.1:3306/rag_demo?charset=utf8mb4"
    )
    secret_key: str = os.getenv("KB_SECRET_KEY", "dev-only-secret-key-change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("KB_TOKEN_EXPIRE_MINUTES", "1440"))

    # MinIO（对象存储，用于头像 / 文档插图）；连接到一个已有的 MinIO 实例
    minio_endpoint: str = os.getenv("KB_MINIO_ENDPOINT", "127.0.0.1:9000")
    minio_access_key: str = os.getenv("KB_MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("KB_MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("KB_MINIO_BUCKET", "rag-kb")
    minio_secure: bool = os.getenv("KB_MINIO_SECURE", "false").lower() == "true"
    # 浏览器可访问的地址，留空则等于 minio_endpoint；MinIO 位于反向代理/内网地址之后时用此项覆盖
    minio_public_endpoint: str = os.getenv("KB_MINIO_PUBLIC_ENDPOINT", "")


settings = Settings()
