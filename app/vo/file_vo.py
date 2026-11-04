from pydantic import BaseModel


class FileVO(BaseModel):
    """文件上传成功后返回的信息。"""
    url: str
    object_name: str
