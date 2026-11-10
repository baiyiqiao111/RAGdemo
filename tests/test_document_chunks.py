import os
import tempfile

# 仅在单独运行本文件时生效：若 test_api.py 已先导入 app.main，engine/SessionLocal/settings 已固定，
# 这里设置的路径不会再被读取，实际会复用 test_api.py 的数据库和 Milvus Lite 临时文件（用户名/知识库标题需避免冲突）
_db_file = os.path.join(tempfile.mkdtemp(), "test_chunks.db")
os.environ["KB_DATABASE_URL"] = "sqlite:///" + _db_file.replace("\\", "/")
os.environ["KB_MILVUS_URI"] = os.path.join(tempfile.mkdtemp(), "test_chunks_milvus.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.config.database import SessionLocal  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.entity import DocumentChunk  # noqa: E402
from app.main import app  # noqa: E402
from app.util.chunk_util import split_into_chunks  # noqa: E402
from app.util.embedding_util import get_embedding_model  # noqa: E402
from app.util.vector_store import VectorStore  # noqa: E402

client = TestClient(app)


def _auth(username, password="secret123"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def _chunks_for(document_id):
    db = SessionLocal()
    try:
        rows = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        return [(r.chunk_index, r.content, r.char_count, r.knowledge_base_id) for r in rows]
    finally:
        db.close()


def _chunk_ids_for(document_id):
    db = SessionLocal()
    try:
        return [
            r.id for r in db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        ]
    finally:
        db.close()


def _vector_store():
    # 复用已加载的 embedding 模型单例拿维度，避免测试里重复加载模型
    return VectorStore(dimension=get_embedding_model().dimension, uri=settings.milvus_uri)


def test_creating_document_auto_generates_chunks():
    """新建文档时应该自动按正文生成切片，顺序和数量与 split_into_chunks 的结果一致。"""
    admin = _auth("chunkadmin")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "切片测试知识库"}).json()

    content = "。".join(f"第{i}段落内容，介绍一些背景信息" for i in range(40)) + "。"
    doc = client.post(
        "/api/documents", headers=admin, json={"title": "长文档", "content": content, "knowledge_base_id": kb["id"]},
    ).json()

    chunks = _chunks_for(doc["id"])
    expected = split_into_chunks(content)
    assert len(chunks) == len(expected)
    assert [c[1] for c in chunks] == expected
    assert [c[0] for c in chunks] == list(range(len(expected)))
    assert all(c[3] == kb["id"] for c in chunks)
    assert all(c[2] == len(c[1]) for c in chunks)


def test_short_document_still_gets_a_single_chunk():
    """内容很短的文档也应该生成（恰好一个）切片，而不是完全没有记录。"""
    admin = _auth("chunkadmin2")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "短文档知识库"}).json()
    doc = client.post(
        "/api/documents", headers=admin, json={"title": "短文档", "content": "一句话内容", "knowledge_base_id": kb["id"]},
    ).json()

    chunks = _chunks_for(doc["id"])
    assert chunks == [(0, "一句话内容", len("一句话内容"), kb["id"])]


def test_empty_document_has_no_chunks():
    """空正文的文档不应该生成任何切片。"""
    admin = _auth("chunkadmin3")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "空文档知识库"}).json()
    doc = client.post(
        "/api/documents", headers=admin, json={"title": "空文档", "content": "", "knowledge_base_id": kb["id"]},
    ).json()

    assert _chunks_for(doc["id"]) == []


def test_creating_document_indexes_chunks_into_vector_store():
    """新建文档时，每个切片都应该被向量化并写入 Milvus Lite，向量主键复用切片的 id。"""
    admin = _auth("chunkadmin6")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "向量化测试知识库"}).json()

    content = "。".join(f"第{i}段关于请假与报销流程的说明文字" for i in range(30)) + "。"
    doc = client.post(
        "/api/documents", headers=admin, json={"title": "向量化文档", "content": content, "knowledge_base_id": kb["id"]},
    ).json()

    chunk_ids = _chunk_ids_for(doc["id"])
    assert len(chunk_ids) > 1  # 内容够长，确保不止一个切片，才能验证“每个”切片都被处理了

    store = _vector_store()
    rows = store.get(chunk_ids)
    assert {r["id"] for r in rows} == set(chunk_ids)
    assert all(r["document_id"] == doc["id"] for r in rows)
    assert all(r["knowledge_base_id"] == kb["id"] for r in rows)

    # 检索能力的基本验证：拿第一个切片的文本去向量化检索，应该能命中它自己（相似度最高）
    first_chunk_text = _chunks_for(doc["id"])[0][1]
    query_vector = get_embedding_model().embed_one(first_chunk_text)
    search_results = store.search(query_vector, top_k=1, document_id=doc["id"])
    assert search_results[0]["id"] == chunk_ids[0]


def test_deleting_document_removes_its_chunks_async():
    """删除文档（含子文档）后台异步清理切片：TestClient 内会同步跑完后台任务，删除接口返回后切片应已清空。"""
    admin = _auth("chunkadmin4")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "删除切片知识库"}).json()
    parent = client.post(
        "/api/documents", headers=admin, json={"title": "父文档", "content": "父文档内容", "knowledge_base_id": kb["id"]},
    ).json()
    child = client.post(
        "/api/documents", headers=admin,
        json={"title": "子文档", "content": "子文档内容", "parent_id": parent["id"], "knowledge_base_id": kb["id"]},
    ).json()
    assert _chunks_for(parent["id"]) != []
    assert _chunks_for(child["id"]) != []

    r = client.delete(f"/api/documents/{parent['id']}", headers=admin)
    assert r.status_code == 204

    assert _chunks_for(parent["id"]) == []
    assert _chunks_for(child["id"]) == []  # 子文档一起被软删除，切片也一起清理


def test_deleting_knowledge_base_removes_all_its_chunks_async():
    """删除知识库后台异步清理库内所有文档的切片。"""
    admin = _auth("chunkadmin5")
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "删除知识库切片测试"}).json()
    doc1 = client.post(
        "/api/documents", headers=admin, json={"title": "文档一", "content": "文档一内容", "knowledge_base_id": kb["id"]},
    ).json()
    doc2 = client.post(
        "/api/documents", headers=admin, json={"title": "文档二", "content": "文档二内容", "knowledge_base_id": kb["id"]},
    ).json()
    assert _chunks_for(doc1["id"]) != []
    assert _chunks_for(doc2["id"]) != []

    r = client.delete(f"/api/knowledge-bases/{kb['id']}", headers=admin)
    assert r.status_code == 204

    assert _chunks_for(doc1["id"]) == []
    assert _chunks_for(doc2["id"]) == []
    assert client.get(f"/api/knowledge-bases/{kb['id']}", headers=admin).status_code == 404
    assert client.get(f"/api/documents/{doc1['id']}", headers=admin).status_code == 404
