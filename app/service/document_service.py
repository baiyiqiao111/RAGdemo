from datetime import datetime
from typing import List, Optional, Set

from fastapi import Depends
from sqlalchemy.orm import Session

from ..common.exceptions import BadRequestException, ConflictException, NotFoundException
from ..config.database import get_db
from ..dto.document_dto import DocumentCreateDTO, DocumentQueryDTO, DocumentUpdateDTO
from ..entity import Document, DocumentChunk, User
from ..mapper.document_chunk_mapper import DocumentChunkMapper
from ..mapper.document_mapper import DocumentMapper
from ..mapper.user_mapper import UserMapper
from ..service.access_control import AccessControl
from ..service.knowledge_base_service import KnowledgeBaseService
from ..util.chunk_util import split_into_chunks
from ..util.text_util import content_meta
from ..vo.document_vo import DocumentBriefVO, DocumentVO
from ..vo.page_vo import PageVO
from ..vo.user_vo import UserBriefVO


class DocumentService:
    """文档相关业务：目录树、分页、增删改查、乐观锁、级联软删除。

    访问控制：读取需要读权限，编辑需要写权限，新建/删除需要知识库（或文档）的管理权限；
    文档权限可继承自所属知识库的权限，见 AccessControl。
    """

    def __init__(
        self,
        db: Session = Depends(get_db),
        document_mapper: DocumentMapper = Depends(),
        document_chunk_mapper: DocumentChunkMapper = Depends(),
        user_mapper: UserMapper = Depends(),
        knowledge_base_service: KnowledgeBaseService = Depends(),
        access_control: AccessControl = Depends(),
    ):
        """构造器注入数据库会话（用于提交事务）、各 Mapper、KnowledgeBaseService 和 AccessControl。"""
        self.db = db
        self.document_mapper = document_mapper
        self.document_chunk_mapper = document_chunk_mapper
        self.user_mapper = user_mapper
        self.knowledge_base_service = knowledge_base_service
        self.access_control = access_control

    # ========================= 查询 =========================

    def tree(self, knowledge_base_id: int, current: User) -> List[DocumentBriefVO]:
        """返回某知识库下全部未删除文档（不含正文），前端按 parent_id 组装目录树；需要该知识库的读权限。"""
        self.knowledge_base_service.get_alive(knowledge_base_id)
        self.access_control.require_access(current, "read", "knowledge_base", knowledge_base_id)
        return [DocumentBriefVO.model_validate(d) for d in self.document_mapper.select_alive_all(knowledge_base_id)]

    def page(self, query: DocumentQueryDTO, current: User) -> PageVO[DocumentBriefVO]:
        """按标题关键字、知识库、父文档分页查询，按更新时间倒序。

        指定了知识库时需要该知识库的读权限；不指定（跨知识库搜索）仅系统管理员可用。
        """
        if query.knowledge_base_id is not None:
            self.access_control.require_access(current, "read", "knowledge_base", query.knowledge_base_id)
        elif current.role != "admin":
            raise BadRequestException("请指定要查询的知识库")

        total = self.document_mapper.count_alive(query.keyword, query.knowledge_base_id, query.parent_id)
        docs = self.document_mapper.select_alive_page(
            query.keyword, query.knowledge_base_id, query.parent_id,
            offset=(query.page - 1) * query.size, limit=query.size,
        )
        return PageVO[DocumentBriefVO](total=total, items=[DocumentBriefVO.model_validate(d) for d in docs])

    def detail(self, doc_id: int, current: User) -> DocumentVO:
        """获取单个文档详情（含正文），需要读权限（可来自文档本身或所属知识库）。"""
        doc = self._get_alive(doc_id)
        self.access_control.require_access(current, "read", "document", doc_id, doc.knowledge_base_id)
        return self._to_vo(doc)

    # ========================= 写操作 =========================

    def create(self, dto: DocumentCreateDTO, current: User) -> DocumentVO:
        """新建文档，必须归属于一个已存在的知识库，且需要该知识库的管理权限；当前用户同时作为创建人和最后编辑人。"""
        self.knowledge_base_service.get_alive(dto.knowledge_base_id)
        self.access_control.require_access(current, "admin", "knowledge_base", dto.knowledge_base_id)
        self._check_parent(dto.parent_id, dto.knowledge_base_id)
        word_count, content_hash = content_meta(dto.content)
        doc = Document(
            knowledge_base_id=dto.knowledge_base_id,
            title=dto.title,
            content=dto.content,
            parent_id=dto.parent_id,
            sort_order=dto.sort_order,
            word_count=word_count,
            content_hash=content_hash,
            creator_id=current.id,
            updater_id=current.id,
        )
        self.document_mapper.insert(doc)
        self._create_chunks(doc)
        self.db.commit()
        self.document_mapper.refresh(doc)
        return self._to_vo(doc)

    def update(self, doc_id: int, dto: DocumentUpdateDTO, current: User) -> DocumentVO:
        """编辑文档，只更新传入的字段；需要写权限；通过版本号做乐观锁，版本不一致抛 409。"""
        doc = self._get_alive(doc_id)
        self.access_control.require_access(current, "write", "document", doc_id, doc.knowledge_base_id)
        fields = dto.model_dump(exclude_unset=True, exclude={"version"})

        values = {}
        if fields.get("title") is not None:
            values["title"] = fields["title"]
        if fields.get("content") is not None:
            values["content"] = fields["content"]
            values["word_count"], values["content_hash"] = content_meta(fields["content"])
        if "parent_id" in fields:  # 显式传 null 表示移动到根目录
            self._check_parent(fields["parent_id"], doc.knowledge_base_id, self_id=doc.id)
            values["parent_id"] = fields["parent_id"]
        if fields.get("sort_order") is not None:
            values["sort_order"] = fields["sort_order"]
        if not values:
            return self._to_vo(doc)

        values.update(updater_id=current.id, updated_at=datetime.now())
        # 乐观锁：只有版本号匹配才更新，避免两个人同时编辑时后保存的人悄悄覆盖前者
        if self.document_mapper.update_by_id_and_version(doc_id, dto.version, values) == 0:
            self.db.rollback()
            raise ConflictException("文档已被他人修改，请刷新后再编辑")
        self.db.commit()
        self.document_mapper.refresh(doc)
        return self._to_vo(doc)

    def delete(self, doc_id: int, current: User) -> None:
        """软删除文档及其全部子文档，需要管理权限（可来自文档本身或所属知识库）。"""
        doc = self._get_alive(doc_id)
        self.access_control.require_access(current, "admin", "document", doc_id, doc.knowledge_base_id)

        # 软删除：连同所有子文档一起放入"回收站"
        ids = self._descendant_ids(doc.id) | {doc.id}
        self.document_mapper.soft_delete_by_ids(ids, datetime.now())
        self.db.commit()

    # ========================= 私有方法 =========================

    def _create_chunks(self, doc: Document) -> None:
        """新建文档时，把正文切分成片段落库，供后续 RAG 向量化/检索使用。"""
        pieces = split_into_chunks(doc.content)
        chunks = [
            DocumentChunk(
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                chunk_index=index,
                content=piece,
                char_count=len(piece),
            )
            for index, piece in enumerate(pieces)
        ]
        self.document_chunk_mapper.insert_many(chunks)

    def _get_alive(self, doc_id: int) -> Document:
        """按 id 获取未删除的文档，不存在或已删除时抛 404。"""
        doc = self.document_mapper.select_by_id(doc_id)
        if doc is None or doc.is_deleted:
            raise NotFoundException("文档不存在")
        return doc

    def _descendant_ids(self, root_id: int) -> Set[int]:
        """逐层查出所有未删除的子孙文档 id（不含自身）。"""
        result: Set[int] = set()
        frontier = [root_id]
        while frontier:
            children = self.document_mapper.select_alive_child_ids(frontier)
            frontier = [c for c in children if c not in result]
            result.update(frontier)
        return result

    def _check_parent(self, parent_id: Optional[int], knowledge_base_id: int, self_id: Optional[int] = None) -> None:
        """校验父文档存在、未删除且属于同一知识库；编辑时还要防止把文档移动到自身或其子文档下形成环。"""
        if parent_id is None:
            return
        parent = self._get_alive(parent_id)
        if parent.knowledge_base_id != knowledge_base_id:
            raise BadRequestException("父文档必须和当前文档属于同一个知识库")
        if self_id is not None and (parent_id == self_id or parent_id in self._descendant_ids(self_id)):
            raise BadRequestException("不能移动到自身或其子文档下")

    def _to_vo(self, doc: Document) -> DocumentVO:
        """将文档实体转换为详情 VO，并补充创建人/编辑人信息。"""
        vo = DocumentVO.model_validate(doc)
        users = {u.id: u for u in self.user_mapper.select_by_ids({doc.creator_id, doc.updater_id})}
        if doc.creator_id in users:
            vo.creator = UserBriefVO.model_validate(users[doc.creator_id])
        if doc.updater_id in users:
            vo.updater = UserBriefVO.model_validate(users[doc.updater_id])
        return vo
