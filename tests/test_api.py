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
def outsider():
    """没有任何额外授权的普通用户，用于验证权限校验确实生效。"""
    return _auth("carol")


@pytest.fixture(scope="module")
def kb(admin, member):
    """测试用知识库：admin 创建（自动获得管理权限），并邀请 member 获得管理权限以便测试多用户文档操作。"""
    created = client.post("/api/knowledge-bases", headers=admin, json={"title": "测试知识库", "description": "用于单测"}).json()
    client.post("/api/permissions/invite", headers=admin, json={
        "username": "bob", "permission_type": "admin", "target_type": "knowledge_base", "target_id": created["id"],
    })
    return created


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

    # 不同知识库下不能挂父子关系（用 admin 提交以越过权限校验，单独验证这条业务规则）
    other_kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "另一个知识库"}).json()
    r = client.post(
        "/api/documents", headers=admin,
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


def test_delete_permission_and_cascade(admin, member, kb, outsider):
    """测试删除权限校验以及父文档删除时子文档级联软删除。"""
    parent = client.post("/api/documents", headers=admin, json={"title": "管理员文档", "knowledge_base_id": kb["id"]}).json()
    child = client.post(
        "/api/documents", headers=member,
        json={"title": "子文档", "parent_id": parent["id"], "knowledge_base_id": kb["id"]},
    ).json()

    # 没有该知识库权限的用户不能删除其中的文档
    assert client.delete(f"/api/documents/{parent['id']}", headers=outsider).status_code == 403

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


def test_access_control_tiers(admin, outsider):
    """测试读/写/管理三级权限分别生效：无权限不能访问，读权限不能改，写权限不能增删，管理权限才能增删。"""
    kb = client.post("/api/knowledge-bases", headers=admin, json={"title": "权限分级知识库"}).json()
    doc = client.post("/api/documents", headers=admin, json={"title": "初始文档", "knowledge_base_id": kb["id"]}).json()

    # 完全没有权限：看不到该知识库，看不了文档，改不了，删不了
    assert kb["id"] not in {k["id"] for k in client.get("/api/knowledge-bases", headers=outsider).json()}
    assert client.get(f"/api/knowledge-bases/{kb['id']}", headers=outsider).status_code == 403
    no_access = client.get("/api/permissions/check", headers=outsider,
                            params={"target_type": "knowledge_base", "target_id": kb["id"]}).json()
    assert no_access == {"read": False, "write": False, "admin": False}
    assert client.get(f"/api/documents/{doc['id']}", headers=outsider).status_code == 403
    assert client.get("/api/documents/tree", headers=outsider, params={"knowledge_base_id": kb["id"]}).status_code == 403
    assert client.put(f"/api/documents/{doc['id']}", headers=outsider, json={"title": "x", "version": 1}).status_code == 403
    assert client.post(
        "/api/documents", headers=outsider, json={"title": "x", "knowledge_base_id": kb["id"]}
    ).status_code == 403
    assert client.delete(f"/api/documents/{doc['id']}", headers=outsider).status_code == 403

    # 申请并通过「读权限」：能看，不能改也不能增删
    apply_r = client.post("/api/permissions/apply", headers=outsider, json={
        "permission_type": "read", "target_type": "knowledge_base", "target_id": kb["id"],
    }).json()
    client.post(f"/api/permissions/{apply_r['id']}/review", headers=admin, json={"approve": True})

    assert client.get(f"/api/knowledge-bases/{kb['id']}", headers=outsider).status_code == 200
    assert client.get(f"/api/documents/{doc['id']}", headers=outsider).status_code == 200
    read_only = client.get("/api/permissions/check", headers=outsider,
                            params={"target_type": "document", "target_id": doc["id"]}).json()
    assert read_only == {"read": True, "write": False, "admin": False}
    assert client.put(f"/api/documents/{doc['id']}", headers=outsider, json={"title": "x", "version": 1}).status_code == 403
    assert client.post(
        "/api/documents", headers=outsider, json={"title": "x", "knowledge_base_id": kb["id"]}
    ).status_code == 403
    assert client.delete(f"/api/documents/{doc['id']}", headers=outsider).status_code == 403

    # 邀请升级为「写权限」：能改了，依然不能增删
    client.post("/api/permissions/invite", headers=admin, json={
        "username": "carol", "permission_type": "write", "target_type": "knowledge_base", "target_id": kb["id"],
    })
    r = client.put(f"/api/documents/{doc['id']}", headers=outsider, json={"title": "改过的标题", "version": 1})
    assert r.status_code == 200 and r.json()["title"] == "改过的标题"
    assert client.post(
        "/api/documents", headers=outsider, json={"title": "x", "knowledge_base_id": kb["id"]}
    ).status_code == 403
    assert client.delete(f"/api/documents/{doc['id']}", headers=outsider).status_code == 403

    # 邀请升级为「管理权限」：才能新建 / 删除
    client.post("/api/permissions/invite", headers=admin, json={
        "username": "carol", "permission_type": "admin", "target_type": "knowledge_base", "target_id": kb["id"],
    })
    new_doc = client.post(
        "/api/documents", headers=outsider, json={"title": "新文档", "knowledge_base_id": kb["id"]}
    )
    assert new_doc.status_code == 201
    assert client.delete(f"/api/documents/{new_doc.json()['id']}", headers=outsider).status_code == 204


def test_notifications(admin, kb):
    """测试申请权限时给审批人生成待办通知：点开可手动标记已读，审批后自动清除该待办。"""
    applicant = _auth("dave")
    other = _auth("erin")  # 对该知识库没有管理权限，不应该收到通知

    # ---- 场景一：申请后生成待办，手动点开标记已读，再审批通过 ----
    before = client.get("/api/notifications/unread-count", headers=admin).json()["count"]
    apply_read = client.post("/api/permissions/apply", headers=applicant, json={
        "permission_type": "read", "target_type": "knowledge_base", "target_id": kb["id"],
    }).json()
    assert client.get("/api/notifications/unread-count", headers=admin).json()["count"] == before + 1

    notifications = client.get("/api/notifications", headers=admin, params={"unread_only": True}).json()
    mine = next(n for n in notifications if n["permission_id"] == apply_read["id"])
    assert mine["is_read"] is False
    assert mine["target_type"] == "knowledge_base" and mine["target_id"] == kb["id"]
    assert "dave" in mine["title"]

    marked = client.post(f"/api/notifications/{mine['id']}/read", headers=admin).json()
    assert marked["is_read"] is True
    assert client.get("/api/notifications/unread-count", headers=admin).json()["count"] == before

    client.post(f"/api/permissions/{apply_read['id']}/review", headers=admin, json={"approve": True})

    # ---- 场景二：再申请一次，这次直接审批（不手动点开），待办应自动清零 ----
    apply_write = client.post("/api/permissions/apply", headers=applicant, json={
        "permission_type": "write", "target_type": "knowledge_base", "target_id": kb["id"],
    }).json()
    before2 = client.get("/api/notifications/unread-count", headers=admin).json()["count"]
    assert before2 == before + 1
    client.post(f"/api/permissions/{apply_write['id']}/review", headers=admin, json={"approve": True})
    assert client.get("/api/notifications/unread-count", headers=admin).json()["count"] == before

    # ---- 场景三：没有管理权限的人不会收到通知 ----
    before3 = client.get("/api/notifications/unread-count", headers=other).json()["count"]
    client.post("/api/permissions/apply", headers=applicant, json={
        "permission_type": "admin", "target_type": "knowledge_base", "target_id": kb["id"],
    })
    assert client.get("/api/notifications/unread-count", headers=other).json()["count"] == before3


def test_invite_links(admin, member, outsider, kb):
    """测试邀请链接：生成、权限校验、单次兑换自动获得权限、兑换后失效、撤销。"""
    # 没有管理权限的人不能生成邀请链接
    r = client.post("/api/invite-links", headers=outsider, json={
        "target_type": "knowledge_base", "target_id": kb["id"], "permission_type": "read",
    })
    assert r.status_code == 403

    # admin（知识库创建者）生成一条读权限邀请链接
    link = client.post("/api/invite-links", headers=admin, json={
        "target_type": "knowledge_base", "target_id": kb["id"], "permission_type": "read",
    }).json()
    assert link["permission_id"] is None and link["is_revoked"] is False

    # 只有管理权限持有者能看到链接列表
    assert client.get("/api/invite-links", headers=outsider,
                       params={"target_type": "knowledge_base", "target_id": kb["id"]}).status_code == 403
    links = client.get("/api/invite-links", headers=admin,
                        params={"target_type": "knowledge_base", "target_id": kb["id"]}).json()
    assert any(l["id"] == link["id"] for l in links)

    # outsider 兑换链接，自动获得读权限
    assert client.get(f"/api/knowledge-bases/{kb['id']}", headers=outsider).status_code == 403
    redeemed = client.post("/api/invite-links/redeem", headers=outsider, json={"token": link["token"]}).json()
    assert redeemed == {"target_type": "knowledge_base", "target_id": kb["id"], "permission_type": "read"}
    assert client.get(f"/api/knowledge-bases/{kb['id']}", headers=outsider).status_code == 200
    tmp_doc = client.post("/api/documents", headers=admin, json={"title": "tmp", "knowledge_base_id": kb["id"]}).json()
    r = client.put(f"/api/documents/{tmp_doc['id']}", headers=outsider, json={"title": "x", "version": 1})
    assert r.status_code == 403  # 只有读权限，不能写

    # 链接绑定了兑换产生的权限记录，列表里能看到是谁、什么时候兑换的
    link_after = client.get("/api/invite-links", headers=admin,
                             params={"target_type": "knowledge_base", "target_id": kb["id"]}).json()
    used_link = next(l for l in link_after if l["id"] == link["id"])
    assert used_link["permission_id"] is not None
    assert used_link["redeemed_by"]["nickname"] == "carol"

    # 每条链接只能兑换一次：同一个人或其他人再次使用同一个 token 都会失败
    assert client.post("/api/invite-links/redeem", headers=outsider, json={"token": link["token"]}).status_code == 400
    frank = _auth("frank")
    assert client.post("/api/invite-links/redeem", headers=frank, json={"token": link["token"]}).status_code == 400

    # 撤销一条还未被使用的链接后，不能再被兑换
    revocable = client.post("/api/invite-links", headers=admin, json={
        "target_type": "knowledge_base", "target_id": kb["id"], "permission_type": "read",
    }).json()
    assert client.delete(f"/api/invite-links/{revocable['id']}", headers=member).status_code == 204  # member 也有该库管理权限
    assert client.post("/api/invite-links/redeem", headers=frank, json={"token": revocable["token"]}).status_code == 400

    # 无效 token
    assert client.post("/api/invite-links/redeem", headers=frank, json={"token": "not-a-real-token"}).status_code == 404
