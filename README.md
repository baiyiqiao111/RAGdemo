# RAG 企业知识库 —— 文档管理基础模块

类似语雀的文档管理：注册登录、目录树、Markdown 文档的新建 / 编辑 / 删除 / 查看。

## 运行

```bash
cd rag_kb
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- 页面：http://127.0.0.1:8000/
- 接口文档（Swagger）：http://127.0.0.1:8000/docs
- 第一个注册的账号自动成为管理员

## 配置（环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KB_DATABASE_URL` | `mysql+pymysql://root:root@127.0.0.1:3306/rag_demo?charset=utf8mb4` | 本地开发也可用 SQLite：`sqlite:///./rag_kb.db` |
| `KB_SECRET_KEY` | 开发用默认值 | JWT 签名密钥，**生产必须修改** |
| `KB_TOKEN_EXPIRE_MINUTES` | `1440` | 登录有效期（分钟） |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/documents/tree` | 目录树（全部文档，不含正文） |
| GET | `/api/documents?keyword=&parent_id=&page=&size=` | 分页列表 / 标题搜索 |
| POST | `/api/documents` | 新建 |
| GET | `/api/documents/{id}` | 查看 |
| PUT | `/api/documents/{id}` | 编辑（需带 `version`，冲突返回 409） |
| DELETE | `/api/documents/{id}` | 删除（软删除，连同子文档） |

## 项目结构（参照 Java / Spring Boot 分层）

```
app/
├── main.py              # 启动入口（≈ @SpringBootApplication）
├── config/              # settings.py 配置（≈ application.yml）、database.py 数据源与会话
├── controller/          # 接收参数、调用 Service、返回 VO（≈ @RestController）
├── service/             # 业务规则与事务提交（≈ @Service + @Transactional）
├── mapper/              # 只做数据库读写，不含业务、不提交事务（≈ MyBatis Mapper）
├── entity/              # ORM 实体，对应数据库表（≈ @Entity / DO）
├── dto/                 # 请求入参与校验（≈ @RequestBody + @Valid）
├── vo/                  # 返回给前端的视图对象，含通用分页 PageVO
├── security/            # 当前登录用户解析（≈ JWT 过滤器 + @AuthenticationPrincipal）
├── common/              # 业务异常 + 全局异常处理（≈ @RestControllerAdvice）
└── util/                # JWT、密码哈希、字数统计等工具
```

调用方向：`controller → service → mapper → entity`，不允许反向或跨层调用（Controller 不直接访问 Mapper）。
依赖注入用 FastAPI 的 `Depends()`（≈ 构造器注入），同一请求内所有 Mapper / Service 共享同一个数据库会话。

## 权限规则

- 所有登录用户：可查看、新建、编辑任意文档
- 删除：仅文档创建者或管理员

## 测试

```bash
pytest -q tests
```
