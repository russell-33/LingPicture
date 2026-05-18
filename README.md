# LingPicture / 灵图空间

灵图空间是一个面向图片空间管理的智能协同图库系统，后端基于 Spring Boot，AI 能力基于 Python FastAPI 独立服务实现。项目在传统图片上传、空间管理、权限控制、团队协作、图片编辑和空间分析能力之上，引入 LLM、RAG 与多 Agent 工作流，实现图片语义搜索、自动标注、批量标签整理和多轮对话式图片管理。

项目的核心设计不是把 AI 做成独立聊天机器人，而是让 AI 服务通过 Java 后端的内部接口参与真实图片管理业务：Java 负责鉴权、空间权限、数据落库和业务一致性，Python AI 服务负责模型调用、RAG 检索、工具编排和上下文管理。

## 项目结构

```text
.
├── yu-picture-backend/    # Spring Boot 业务后端
├── ai-service/            # Python FastAPI AI 服务
└── yu-picture-frontend/   # Vue 3 前端
```

## 技术栈

**Java 后端**

- Spring Boot 2.7
- MyBatis-Plus
- MySQL
- Redis / Spring Session
- Sa-Token 权限认证
- WebSocket / Disruptor
- 腾讯云 COS
- Knife4j

**AI 服务**

- Python FastAPI
- LangGraph / LangChain
- DashScope OpenAI-compatible API
- ChromaDB
- BM25 / Jieba
- qwen3-rerank
- Redis 会话记忆
- Qwen tokenizer 上下文预算

**前端**

- Vue 3
- Vite
- TypeScript
- Ant Design Vue
- ECharts

## Java 后端能力

Java 后端是系统的业务主干，所有真实数据操作都经过 Spring Boot 服务层完成。

主要模块：

- 用户模块：注册、登录、当前用户、管理员用户管理。
- 图片模块：文件上传、URL 上传、图片删除、图片编辑、审核、颜色搜索、批量上传、批量编辑。
- 空间模块：私有空间、团队空间、空间额度、空间成员、空间权限。
- 空间分析：容量用量、分类统计、标签统计、图片大小分布、用户上传行为、空间排行。
- 协作编辑：基于 WebSocket 的图片编辑协同状态同步。
- AI 网关：统一代理前端到 Python AI 服务的调用，并补充用户身份和空间权限校验。
- 内部接口：供 Python AI 服务查询图片详情、执行图片编辑、空间分析、保存 Agent 会话摘要和操作日志。

AI 相关 Java 入口：

- `AiController`
  - `/ai/agent/run/stream`：代理多 Agent SSE 流式任务。
  - `/ai/agent/messages`：读取 AI 助手历史消息。
  - `/ai/picture/auto-tag/{pictureId}`：触发图片自动标注。
  - `/ai/internal/context/session-summary`：AI 会话摘要持久化。
  - `/ai/internal/context/operation-log`：AI 工具操作日志持久化。

- `PictureController`
  - `/picture/get/vo/internal`：AI 服务读取图片详情。
  - `/picture/list/page/vo/internal`：AI 服务按数据库条件检索图片。
  - `/picture/edit/internal`：AI 服务执行受控图片编辑。
  - 删除图片时会调用 AI 索引清理客户端，避免 ChromaDB / BM25 出现脏索引。

- `SpaceAnalyzeController`
  - `/space/analyze/*/internal`：AI 服务复用真实空间分析能力。

内部调用通过 `X-Internal-Token` 做服务间鉴权，并通过 `X-Internal-User-Id` 传递用户上下文。Java 层仍会校验空间权限和图片归属，避免 AI 服务绕过原有权限体系直接操作数据。

## AI 服务能力

AI 服务位于 `ai-service/`，通过 FastAPI 对 Java 后端提供内部能力。

主要路由：

- `/api/v1/agent/run`：同步执行多 Agent 任务。
- `/api/v1/agent/run/stream`：SSE 流式执行多 Agent 任务。
- `/api/v1/agent/messages/{session_id}`：读取会话消息。
- `/api/v1/rag/picture/search`：图片语义搜索。
- `/api/v1/rag/picture/index`：构建图片索引。
- `/api/v1/rag/picture/index/{picture_id}`：删除图片索引。
- `/api/v1/picture/auto-tag/{picture_id}`：图片自动标注。

### 多 Agent 工作流

AI 助手采用 Supervisor + Expert 的多 Agent 结构：

- Supervisor：分析用户自然语言任务，拆解为搜索、编辑、分析等子任务。
- Searcher：负责图片搜索、语义检索、标签检索和结果整理。
- Editor：负责图片标签、分类、名称、简介等批量编辑。
- Analyst：负责空间使用情况分析。

典型任务：

```text
先给有关赛车的图片加上 Racing 标签，然后分析当前空间
```

执行链路：

```text
用户输入
 -> Java AiController 校验登录态和空间权限
 -> Python Supervisor 规划任务
 -> Searcher 搜索图片
 -> Editor 批量编辑标签
 -> Analyst 调用空间分析工具
 -> Java 内部接口落库 / 查询真实业务数据
 -> 前端 SSE 展示最终结果
```

### RAG 图片语义检索

图片搜索链路不是只查数据库，而是结合语义检索和业务数据库检索：

```text
Query 改写
 -> ChromaDB 向量召回
 -> BM25 关键词召回
 -> 多路结果去重融合
 -> qwen3-rerank 重排序
 -> Java 详情接口校验图片是否仍存在
 -> 返回可展示结果
```

其中：

- 向量检索用于召回视觉语义相关图片。
- BM25 用于补充标签、名称、简介中的关键词匹配。
- Java 数据库检索用于补齐业务字段和精确标签场景。
- Rerank 用于将更相关的图片提前。
- 删除图片时会同步清理 AI 索引，降低旧图片被召回的概率。

### 上下文管理

AI 服务支持多轮对话和指代场景，例如“刚才第二张”“这些图片”等。

上下文来源包括：

- 当前用户输入。
- 可信 `space_id` / `user_id`。
- Redis 中的短期消息历史。
- MySQL 中的长期会话摘要。
- 上一轮工具调用结果，例如最近一次搜索结果、空间分析结果。

上下文进入模型前会经过 Qwen tokenizer 预算和滑动窗口控制，避免长对话或大批量工具结果导致上下文超限。

### 自动标注

图片自动标注链路：

```text
图片 URL
 -> 多模态模型理解图片内容
 -> 结构化生成名称、简介、分类、标签
 -> 标签白名单过滤和数量限制
 -> Java /picture/edit/internal 更新图片信息
```

标签不是任意生成，而是受项目统一标签体系约束，避免 AI 产生过多不可控标签。

## 配置说明

仓库不会提交真实密码、COS 密钥、模型 API Key 或本地 Docker 配置。

已忽略的本地文件包括：

- `.env`
- `ai-service/.env`
- `yu-picture-backend/src/main/resources/application-local.yml`
- `docker-compose.yml`
- `md/`

### Java 后端配置

可提交配置位于：

```text
yu-picture-backend/src/main/resources/application.yml
```

其中敏感项均使用环境变量占位，例如：

```yaml
spring:
  datasource:
    url: ${MYSQL_URL:jdbc:mysql://localhost:3306/yp_picture?...}
    username: ${MYSQL_USERNAME:root}
    password: ${MYSQL_PASSWORD:}

cos:
  client:
    secretId: ${COS_SECRET_ID:}
    secretKey: ${COS_SECRET_KEY:}

aliyunAi:
  apiKey: ${ALIYUN_AI_API_KEY:}

ai:
  service:
    url: ${AI_SERVICE_URL:http://localhost:8000}
    internal-token: ${AI_INTERNAL_TOKEN:}
```

本地开发时可在 `application-local.yml` 中填写真实值，该文件不会提交。

### AI 服务配置

AI 服务示例配置位于：

```text
ai-service/.env.example
```

本地开发时复制为 `.env`：

```bash
cp ai-service/.env.example ai-service/.env
```

需要配置：

- `LLM_API_KEY`
- `EMBEDDING_API_KEY`
- `RERANK_API_KEY`
- `AI_INTERNAL_TOKEN`
- `JAVA_BACKEND_URL`
- Redis / MySQL 连接信息

`AI_INTERNAL_TOKEN` 需要和 Java 后端保持一致。

## 本地启动

### 1. 启动 Java 后端

```bash
cd yu-picture-backend
mvn spring-boot:run
```

默认服务地址：

```text
http://localhost:8123/api
```

### 2. 启动 AI 服务

```bash
cd ai-service
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn src.main:app --reload --port 8000
```

健康检查：

```text
http://localhost:8000/health
```

### 3. 启动前端

```bash
cd yu-picture-frontend
npm install
npm run dev
```

## 验证命令

Java 后端编译：

```bash
cd yu-picture-backend
mvn -q -DskipTests compile
```

AI 服务测试：

```bash
cd ai-service
TRANSFORMERS_OFFLINE=1 python3 -m unittest discover -s tests
```

前端构建：

```bash
cd yu-picture-frontend
npm run build-only
```

## 项目亮点

- 将 Java 图片管理业务和 Python AI 服务分层解耦，Java 保持业务数据和权限边界，Python 负责 LLM、RAG 和 Agent 编排。
- 使用多 Agent 工作流拆分搜索、编辑、分析任务，支持“先找图再编辑再分析空间”等多步骤自然语言操作。
- 构建图片语义搜索链路，结合 ChromaDB 向量检索、BM25 关键词检索、数据库精确检索和 qwen3-rerank 重排序。
- 支持多轮对话上下文、工具结果记忆和会话摘要持久化，能够处理“刚才第二张”“这些图片”等指代场景。
- AI 自动标注接入统一标签体系，通过标签白名单和数量限制降低随机标签污染。
- 删除图片时同步清理 AI 索引，避免向量库和 BM25 缓存召回已删除图片。
- Java 内部接口使用内部 token 和用户上下文校验，AI 服务不能绕过原业务权限直接操作数据。

## 适用场景

- 个人或团队图片空间管理。
- 图片素材检索和标签整理。
- 面向图片管理业务的 AI Agent / RAG 应用实践。
- Java 后端系统接入 Python LLM 服务的工程示例。
