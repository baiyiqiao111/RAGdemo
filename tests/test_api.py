import os
import tempfile

# 测试使用独立的临时数据库，必须在导入 app 之前设置
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["KB_DATABASE_URL"] = "sqlite:///" + _db_file.replace("\\", "/")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _auth(username, password="secret123"):
    """注册并登录指定用户，返回带 Bearer 令牌的请求头。"""
    client.post("/api/auth/register", json={"username": username, "password": password})
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


@pytest.fixture(scope="module")
def admin():
    """管理员用户的请求头（第一个注册的用户）。"""
    return _auth("alice")  # 第一个注册的用户是管理员


@pytest.fixture(scope="module")
def member(admin):
    """普通成员用户的请求头，依赖 admin 以保证注册顺序。"""
    return _auth("bob")


@pytest.fixture(scope="module")
def kb(admin):
    """测试用知识库，文档必须挂在某个知识库下才能创建。"""
    return client.post("/api/knowledge-bases", headers=admin, json={"title": "测试知识库", "description": "用于单测"}).json()


def test_auth(admin, member):
    """测试注册、登录、角色分配及未登录访问拦截。"""
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "admin"
    assert client.get("/api/auth/me", headers=member).json()["role"] == "member"
    assert client.get("/api/documents/tree").status_code == 401
    assert client.post("/api/auth/register", json={"username": "alice", "password": "secret123"}).status_code == 409
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    # 校验失败时返回可读的中文提示
    r = client.post("/api/auth/register", json={"username": "张三", "password": "123"})
    assert r.status_code == 422
    assert "用户名" in r.json()["detail"] and "密码" in r.json()["detail"]


def test_file_upload_validation(member):
    """测试上传接口的鉴权和文件类型/大小校验（不依赖真实 MinIO）。"""
    png = ("a.png", b"\x89PNG\r\n", "image/png")
    assert client.post("/api/files/upload", files={"file": png}).status_code == 401
    r = client.post("/api/files/upload", headers=member, files={"file": ("a.txt", b"hi", "text/plain")})
    assert r.status_code == 400 and "图片" in r.json()["detail"]
    r = client.post("/api/files/upload", headers=member, files={"file": ("a.png", b"0" * (5 * 1024 * 1024 + 1), "image/png")})
    assert r.status_code == 400 and "5MB" in r.json()["detail"]


def test_knowledge_base(admin):
    """测试知识库的新建、列表、详情，以及文档必须归属于已存在的知识库。"""
    created = client.post("/api/knowledge-bases", headers=admin, json={"title": "产品文档", "description": "desc"})
    assert created.status_code == 201
    kb_id = created.json()["id"]
    assert client.get(f"/api/knowledge-bases/{kb_id}", headers=admin).json()["title"] == "产品文档"
    assert kb_id in {k["id"] for k in client.get("/api/knowledge-bases", headers=admin).json()}

    # 不传 knowledge_base_id 建文档 -> 422；指向不存在的知识库 -> 404
    assert client.post("/api/documents", headers=admin, json={"title": "x"}).status_code == 422
    r = client.post("/api/documents", headers=admin, json={"title": "x", "knowledge_base_id": 999999})
    assert r.status_code == 404


def test_document_crud(admin, member, kb):
    # 新建
    """测试文档的新建、查看、列表、目录树、编辑、乐观锁冲突和移动。"""
    r = client.post(
        "/api/documents", headers=member,
        json={"title": "入职指南", "content": "# 欢迎\n第一天", "knowledge_base_id": kb["id"]},
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["word_count"] == len("#欢迎第一天")
    assert doc["version"] == 1 and doc["creator"]["nickname"] == "bob"

    child = client.post(
        "/api/documents", headers=member,
        json={"title": "报销流程", "parent_id": doc["id"], "knowledge_base_id": kb["id"]},
    ).json()

    # 不同知识库下不能挂父子关系
    other_kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "另一个知识库"}).json()
    r = client.post(
        "/api/documents", headers=member,
        json={"title": "跨库子文档", "parent_id": doc["id"], "knowledge_base_id": other_kb["id"]},
    )
    assert r.status_code == 400

    # 查看 / 列表 / 目录树（按知识库过滤）
    assert client.get(f"/api/documents/{doc['id']}", headers=admin).json()["content"] == "# 欢迎\n第一天"
    page = client.get("/api/documents", headers=admin, params={"keyword": "报销", "knowledge_base_id": kb["id"]}).json()
    assert page["total"] == 1 and page["items"][0]["id"] == child["id"]
    tree = client.get("/api/documents/tree", headers=admin, params={"knowledge_base_id": kb["id"]}).json()
    assert {d["id"] for d in tree} >= {doc["id"], child["id"]}
    assert client.get("/api/documents/tree", headers=admin).status_code == 422  # 必须指定知识库

    # 编辑（管理员编辑 bob 的文档）
    r = client.put(f"/api/documents/{doc['id']}", headers=admin, json={"content": "新内容", "version": 1})
    assert r.status_code == 200
    assert r.json()["version"] == 2 and r.json()["updater"]["nickname"] == "alice"
    assert r.json()["title"] == "入职指南"  # 未传的字段保持不变

    # 旧版本号再次提交 -> 冲突
    r = client.put(f"/api/documents/{doc['id']}", headers=member, json={"title": "x", "version": 1})
    assert r.status_code == 409

    # 不能把文档移动到自己的子文档下
    r = client.put(f"/api/documents/{doc['id']}", headers=member, json={"parent_id": child["id"], "version": 2})
    assert r.status_code == 400

    # 显式传 null 移动到根目录
    r = client.put(f"/api/documents/{child['id']}", headers=member, json={"parent_id": None, "version": 1})
    assert r.status_code == 200 and r.json()["parent_id"] is None


def test_delete_permission_and_cascade(admin, member, kb):
    """测试删除权限校验以及父文档删除时子文档级联软删除。"""
    parent = client.post("/api/documents", headers=admin, json={"title": "管理员文档", "knowledge_base_id": kb["id"]}).json()
    child = client.post(
        "/api/documents", headers=member,
        json={"title": "子文档", "parent_id": parent["id"], "knowledge_base_id": kb["id"]},
    ).json()

    # 普通成员不能删除别人创建的文档
    assert client.delete(f"/api/documents/{parent['id']}", headers=member).status_code == 403

    # 删除父文档，子文档一起被软删除
    assert client.delete(f"/api/documents/{parent['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/documents/{parent['id']}", headers=admin).status_code == 404
    assert client.get(f"/api/documents/{child['id']}", headers=admin).status_code == 404
    tree_ids = {d["id"] for d in client.get("/api/documents/tree", headers=admin, params={"knowledge_base_id": kb["id"]}).json()}
    assert parent["id"] not in tree_ids and child["id"] not in tree_ids

    # 不能在已删除的文档下新建
    r = client.post(
        "/api/documents", headers=member,
        json={"title": "x", "parent_id": parent["id"], "knowledge_base_id": kb["id"]},
    )
    assert r.status_code == 404
