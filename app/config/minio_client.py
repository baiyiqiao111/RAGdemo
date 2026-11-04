import json

from minio import Minio

from .settings import settings

# MinIO 客户端单例（≈ S3 客户端 Bean）
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)

_PUBLIC_READ_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"],
        "Resource": [f"arn:aws:s3:::{settings.minio_bucket}/*"],
    }],
})


_bucket_ready = False


def ensure_bucket() -> None:
    """确保桶存在，并开放匿名只读，使头像 / 文档插图能被 <img> 标签直接访问。

    惰性调用（首次上传时才连接 MinIO），避免应用启动/测试在 MinIO 不可用时连带失败。
    """
    global _bucket_ready
    if _bucket_ready:
        return
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)
    minio_client.set_bucket_policy(settings.minio_bucket, _PUBLIC_READ_POLICY)
    _bucket_ready = True


def public_url(object_name: str) -> str:
    """拼接对象的公开访问地址。"""
    base = settings.minio_public_endpoint or settings.minio_endpoint
    scheme = "https" if settings.minio_secure else "http"
    return f"{scheme}://{base}/{settings.minio_bucket}/{object_name}"
