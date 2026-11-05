-- RAG 企业知识库 —— 基础表结构（MySQL 8.0+）
-- 与 app/models.py 保持一致；开发环境下程序启动时会自动建表，此文件供生产环境/DBA 参考

CREATE DATABASE IF NOT EXISTS rag_demo DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rag_demo;

-- ------------------------------------------------------------
-- 用户表
-- ------------------------------------------------------------
CREATE TABLE users (
    id             BIGINT       NOT NULL AUTO_INCREMENT,
    username       VARCHAR(64)  NOT NULL                 COMMENT '登录名',
    password_hash  VARCHAR(255) NOT NULL                 COMMENT 'bcrypt 哈希',
    nickname       VARCHAR(64)  NOT NULL                 COMMENT '显示名称',
    email          VARCHAR(128) NULL                     COMMENT '邮箱',
    avatar_url     VARCHAR(512) NULL                     COMMENT '头像',
    role           VARCHAR(16)  NOT NULL DEFAULT 'member' COMMENT 'admin / member',
    is_active      TINYINT(1)   NOT NULL DEFAULT 1       COMMENT '是否启用',
    last_login_at  DATETIME     NULL                     COMMENT '最后登录时间',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username),
    UNIQUE KEY uk_users_email (email)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户表';

-- ------------------------------------------------------------
-- 知识库表（文档的顶层归属，文档不能脱离知识库独立存在）
-- ------------------------------------------------------------
CREATE TABLE knowledge_bases (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    title       VARCHAR(255) NOT NULL COMMENT '知识库标题',
    description TEXT         NULL     COMMENT '知识库描述',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '知识库表';

-- ------------------------------------------------------------
-- 文档表（parent_id 形成目录树，类似语雀知识库目录；必须归属于一个知识库）
-- ------------------------------------------------------------
CREATE TABLE documents (
    id                BIGINT       NOT NULL AUTO_INCREMENT,
    knowledge_base_id BIGINT       NOT NULL                    COMMENT '所属知识库',
    title             VARCHAR(255) NOT NULL                    COMMENT '标题',
    content           LONGTEXT     NOT NULL                    COMMENT '正文（Markdown）',
    content_format    VARCHAR(16)  NOT NULL DEFAULT 'markdown' COMMENT '正文格式',
    parent_id         BIGINT       NULL                        COMMENT '父文档，NULL 为根节点',
    sort_order        INT          NOT NULL DEFAULT 0          COMMENT '同级排序',
    word_count        INT          NOT NULL DEFAULT 0          COMMENT '字数',
    content_hash      VARCHAR(64)  NOT NULL DEFAULT ''         COMMENT '正文 SHA-256，RAG 判断是否需要重建向量',
    version           INT          NOT NULL DEFAULT 1          COMMENT '版本号，乐观锁',
    creator_id        BIGINT       NOT NULL                    COMMENT '创建人',
    updater_id        BIGINT       NOT NULL                    COMMENT '最后编辑人',
    is_deleted        TINYINT(1)   NOT NULL DEFAULT 0          COMMENT '软删除标记',
    deleted_at        DATETIME     NULL                        COMMENT '删除时间',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_documents_kb (knowledge_base_id),
    KEY ix_documents_parent_sort (parent_id, sort_order),
    KEY ix_documents_creator (creator_id),
    KEY ix_documents_updated (is_deleted, updated_at),
    CONSTRAINT fk_documents_kb      FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id),
    CONSTRAINT fk_documents_parent  FOREIGN KEY (parent_id)  REFERENCES documents (id),
    CONSTRAINT fk_documents_creator FOREIGN KEY (creator_id) REFERENCES users (id),
    CONSTRAINT fk_documents_updater FOREIGN KEY (updater_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '文档表';

-- ------------------------------------------------------------
-- 权限表（对知识库/文档的访问权限申请与审批记录；target_id 按 target_type 区分指向
-- knowledge_bases 或 documents，是多态关联，不建外键，由应用层校验）
-- ------------------------------------------------------------
CREATE TABLE permissions (
    id              BIGINT      NOT NULL AUTO_INCREMENT,
    user_id         BIGINT      NOT NULL                   COMMENT '被授权用户',
    permission_type VARCHAR(16) NOT NULL                   COMMENT 'read / write / admin',
    target_type     VARCHAR(16) NOT NULL                   COMMENT 'knowledge_base / document',
    target_id       BIGINT      NOT NULL                   COMMENT '知识库或文档 id',
    status          VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending / approved / rejected',
    applied_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
    approved_at     DATETIME    NULL                       COMMENT '审批时间',
    inviter_id      BIGINT      NULL                       COMMENT '邀请人：直接邀请的发起人，或自助申请被谁审批通过',
    PRIMARY KEY (id),
    KEY ix_permissions_target (target_type, target_id),
    KEY ix_permissions_user (user_id),
    CONSTRAINT fk_permissions_user    FOREIGN KEY (user_id)    REFERENCES users (id),
    CONSTRAINT fk_permissions_inviter FOREIGN KEY (inviter_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '权限表';

-- ------------------------------------------------------------
-- 系统通知表（目前用于权限申请的待办提醒，点进去可直接审批）
-- ------------------------------------------------------------
CREATE TABLE notifications (
    id            BIGINT      NOT NULL AUTO_INCREMENT,
    user_id       BIGINT      NOT NULL                 COMMENT '接收通知的用户',
    permission_id BIGINT      NULL                     COMMENT '关联的权限申请，用于点进去直接审批',
    target_type   VARCHAR(16) NULL                     COMMENT 'knowledge_base / document，冗余自权限申请',
    target_id     BIGINT      NULL                     COMMENT '知识库或文档 id，冗余自权限申请',
    title         VARCHAR(255) NOT NULL                COMMENT '通知标题',
    content       TEXT        NULL                     COMMENT '通知内容',
    is_read       TINYINT(1)  NOT NULL DEFAULT 0        COMMENT '是否已读',
    created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_notifications_user (user_id, is_read),
    CONSTRAINT fk_notifications_user       FOREIGN KEY (user_id)       REFERENCES users (id),
    CONSTRAINT fk_notifications_permission FOREIGN KEY (permission_id) REFERENCES permissions (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '系统通知表';

-- ------------------------------------------------------------
-- 邀请链接表（分享链接，供单个用户点开自动获得指定权限，兑换一次后即失效；
-- permission_id 绑定兑换时生成的那条权限记录，为空表示尚未被使用）
-- ------------------------------------------------------------
CREATE TABLE invite_links (
    id              BIGINT      NOT NULL AUTO_INCREMENT,
    token           VARCHAR(43) NOT NULL                 COMMENT '邀请令牌，拼在邀请链接里',
    target_type     VARCHAR(16) NOT NULL                 COMMENT 'knowledge_base / document',
    target_id       BIGINT      NOT NULL                 COMMENT '知识库或文档 id',
    permission_type VARCHAR(16) NOT NULL                 COMMENT 'read / write / admin',
    created_by      BIGINT      NOT NULL                 COMMENT '创建者',
    permission_id   BIGINT      NULL                     COMMENT '兑换后绑定的权限记录，NULL 表示尚未被使用',
    expires_at      DATETIME    NULL                     COMMENT '过期时间，NULL 为永不过期',
    is_revoked      TINYINT(1)  NOT NULL DEFAULT 0        COMMENT '是否已撤销',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_invite_links_token (token),
    KEY ix_invite_links_target (target_type, target_id),
    CONSTRAINT fk_invite_links_creator   FOREIGN KEY (created_by)    REFERENCES users (id),
    CONSTRAINT fk_invite_links_permission FOREIGN KEY (permission_id) REFERENCES permissions (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '邀请链接表';
