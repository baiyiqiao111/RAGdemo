import uuid
from io import BytesIO

from fastapi import UploadFile

from ..common.exceptions import BadRequestException
from ..config.minio_client import ensure_bucket, minio_client, public_url
from ..config.settings import settings
from ..vo.file_vo import FileVO

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_SIZE_BYTES = 5 * 1024 * 1024


class FileService:
    """文件上传相关业务：图片校验 + 写入 MinIO。"""

    async def upload_image(self, file: UploadFile) -> FileVO:
        """上传头像 / 文档插图，返回可直接访问的 URL；仅允许常见图片格式，限制 5MB。"""
        if file.content_type not in _ALLOWED_CONTENT_TYPES:
            raise BadRequestException("仅支持 jpg/png/gif/webp 图片")

        data = await file.read()
        if len(data) > _MAX_SIZE_BYTES:
            raise BadRequestException("图片大小不能超过 5MB")

        ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "bin"
        object_name = f"{uuid.uuid4().hex}.{ext}"
        ensure_bucket()
        minio_client.put_object(
            settings.minio_bucket, object_name, BytesIO(data), length=len(data), content_type=file.content_type,
        )
        return FileVO(url=public_url(object_name), object_name=object_name)
