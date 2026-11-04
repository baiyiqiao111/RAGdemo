from fastapi import APIRouter, Depends, File, UploadFile, status

from ..entity import User
from ..security.auth_dependency import get_current_user
from ..service.file_service import FileService
from ..vo.file_vo import FileVO

router = APIRouter(prefix="/api/files", tags=["文件"])


@router.post("/upload", response_model=FileVO, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    file_service: FileService = Depends(),
    _: User = Depends(get_current_user),
):
    """上传图片，用于头像或文档插图，返回可直接访问的 URL。"""
    return await file_service.upload_image(file)
