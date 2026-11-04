"""实体层（≈ @Entity / DO），与数据库表一一对应。"""
from .document import Document
from .knowledge_base import KnowledgeBase
from .permission import Permission
from .user import User

__all__ = ["User", "Document", "KnowledgeBase", "Permission"]
