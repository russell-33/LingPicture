create database if not exists yp_picture;
use yp_picture;
-- 用户表
create table if not exists user
(
    id           bigint auto_increment comment 'id' primary key,
    userAccount  varchar(256)                           not null comment '账号',
    userPassword varchar(512)                           not null comment '密码',
    userName     varchar(256)                           null comment '用户昵称',
    userAvatar   varchar(1024)                          null comment '用户头像',
    userProfile  varchar(512)                           null comment '用户简介',
    userRole     varchar(256) default 'user'            not null comment '用户角色：user/admin',
    editTime     datetime     default CURRENT_TIMESTAMP not null comment '编辑时间',
    createTime   datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime   datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete     tinyint      default 0                 not null comment '是否删除',
    UNIQUE KEY uk_userAccount (userAccount),
    INDEX idx_userName (userName)
) comment '用户' collate = utf8mb4_unicode_ci;

-- 图片表
create table if not exists picture
(
    id           bigint auto_increment comment 'id' primary key,
    url          varchar(512)                       not null comment '图片 url',
    name         varchar(128)                       not null comment '图片名称',
    introduction varchar(512)                       null comment '简介',
    category     varchar(64)                        null comment '分类',
    tags         varchar(512)                       null comment '标签（JSON 数组）',
    picSize      bigint                             null comment '图片体积',
    picWidth     int                                null comment '图片宽度',
    picHeight    int                                null comment '图片高度',
    picScale     double                             null comment '图片宽高比例',
    picFormat    varchar(32)                        null comment '图片格式',
    userId       bigint                             not null comment '创建用户 id',
    createTime   datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    editTime     datetime default CURRENT_TIMESTAMP not null comment '编辑时间',
    updateTime   datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete     tinyint  default 0                 not null comment '是否删除',
    INDEX idx_name (name),                 -- 提升基于图片名称的查询性能
    INDEX idx_introduction (introduction), -- 用于模糊搜索图片简介
    INDEX idx_category (category),         -- 提升基于分类的查询性能
    INDEX idx_tags (tags),                 -- 提升基于标签的查询性能
    INDEX idx_userId (userId)              -- 提升基于用户 ID 的查询性能
) comment '图片' collate = utf8mb4_unicode_ci;


ALTER TABLE picture
    -- 添加新列
    ADD COLUMN reviewStatus  INT DEFAULT 0 NOT NULL COMMENT '审核状态：0-待审核; 1-通过; 2-拒绝',
    ADD COLUMN reviewMessage VARCHAR(512)  NULL COMMENT '审核信息',
    ADD COLUMN reviewerId    BIGINT        NULL COMMENT '审核人 ID',
    ADD COLUMN reviewTime    DATETIME      NULL COMMENT '审核时间';

-- 创建基于 reviewStatus 列的索引
CREATE INDEX idx_reviewStatus ON picture (reviewStatus);


alter table picture
    add column thumbnailUrl varchar(512) null comment '缩略图 url';


-- 空间表
create table if not exists space
(
    id         bigint auto_increment comment 'id' primary key,
    spaceName  varchar(128)                       null comment '空间名称',
    spaceLevel int      default 0                 null comment '空间级别：0-普通版 1-专业版 2-旗舰版',
    maxSize    bigint   default 0                 null comment '空间图片的最大总大小',
    maxCount   bigint   default 0                 null comment '空间图片的最大数量',
    totalSize  bigint   default 0                 null comment '当前空间下图片的总大小',
    totalCount bigint   default 0                 null comment '当前空间下的图片数量',
    userId     bigint                             not null comment '创建用户 id',
    createTime datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    editTime   datetime default CURRENT_TIMESTAMP not null comment '编辑时间',
    updateTime datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete   tinyint  default 0                 not null comment '是否删除',
    -- 索引设计
    index idx_userId (userId),        -- 提升基于用户的查询效率
    index idx_spaceName (spaceName),  -- 提升基于空间名称的查询效率
    index idx_spaceLevel (spaceLevel) -- 提升按空间级别查询的效率
) comment '空间' collate = utf8mb4_unicode_ci;


-- 添加新列
ALTER TABLE picture
    ADD COLUMN spaceId bigint null comment '空间 id（为空表示公共空间）';

-- 创建索引
CREATE INDEX idx_spaceId ON picture (spaceId);


alter table picture
    add column picColor varchar(16) null comment '图片主色调';

alter table space
    add column spaceType int default 0 not null comment '空间类型：0-个人空间 1-团队空间';

create index idx_spaceType on space (spaceType);


-- Agent 会话摘要表
create table if not exists agent_session
(
    id              bigint auto_increment comment 'id' primary key,
    sessionId       varchar(128)                       not null comment 'Agent 会话 id',
    userId          bigint                             not null comment '用户 id',
    spaceId         bigint                             null comment '空间 id',
    title           varchar(128)                       null comment '会话标题',
    summary         text                               null comment '长期会话摘要',
    lastMessageTime datetime                           null comment '最后消息时间',
    createTime      datetime default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint  default 0                 not null comment '是否删除',
    unique key uk_sessionId (sessionId),
    index idx_userId (userId),
    index idx_spaceId (spaceId)
) comment 'Agent 会话摘要' collate = utf8mb4_unicode_ci;

-- Agent 业务操作记录表
create table if not exists agent_operation_log
(
    id            bigint auto_increment comment 'id' primary key,
    sessionId     varchar(128)                       not null comment 'Agent 会话 id',
    userId        bigint                             not null comment '用户 id',
    spaceId       bigint                             null comment '空间 id',
    operationType varchar(64)                        not null comment '操作类型',
    toolName      varchar(128)                       null comment '工具名称',
    targetIds     text                               null comment '目标图片或资源 id JSON',
    requestText   text                               null comment '用户原始请求',
    resultSummary text                               null comment '执行结果摘要',
    status        varchar(32) default 'SUCCESS'      not null comment '状态',
    createTime    datetime    default CURRENT_TIMESTAMP not null comment '创建时间',
    index idx_sessionId (sessionId),
    index idx_userId (userId),
    index idx_spaceId (spaceId)
) comment 'Agent 业务操作记录' collate = utf8mb4_unicode_ci;


-- 图片 AI 索引 outbox 表
create table if not exists picture_index_outbox
(
    id            bigint auto_increment comment 'id' primary key,
    eventType     varchar(32)                         not null comment '事件类型：UPSERT/DELETE',
    pictureId     bigint                              not null comment '图片 id',
    spaceId       bigint                              null comment '空间 id',
    payload       text                                not null comment '索引消息 JSON',
    status        varchar(32) default 'PENDING'       not null comment '状态：PENDING/SENT/FAILED',
    retryCount    int         default 0               not null comment '重试次数',
    lastError     varchar(512)                        null comment '最近错误',
    nextRetryTime datetime                            null comment '下次补发时间',
    createTime    datetime    default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime    datetime    default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    index idx_status_nextRetryTime (status, nextRetryTime),
    index idx_pictureId (pictureId),
    index idx_spaceId (spaceId)
) comment '图片 AI 索引 outbox' collate = utf8mb4_unicode_ci;


-- 空间成员表
create table if not exists space_user
(
    id         bigint auto_increment comment 'id' primary key,
    spaceId    bigint                                 not null comment '空间 id',
    userId     bigint                                 not null comment '用户 id',
    spaceRole  varchar(128) default 'viewer'          null comment '空间角色：viewer/editor/admin',
    createTime datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    -- 索引设计
    UNIQUE KEY uk_spaceId_userId (spaceId, userId), -- 唯一索引，用户在一个空间中只能有一个角色
    INDEX idx_spaceId (spaceId),                    -- 提升按空间查询的性能
    INDEX idx_userId (userId)                       -- 提升按用户查询的性能
) comment '空间用户关联' collate = utf8mb4_unicode_ci;


