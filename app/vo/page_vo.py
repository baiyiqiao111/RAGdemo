from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageVO(BaseModel, Generic[T]):
    """通用分页结果（≈ PageResult<T>）：总条数 + 当前页数据。"""
    total: int
    items: List[T]
