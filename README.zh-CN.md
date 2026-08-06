# TARCS-Mem

> 面向 RAG 与 AI Agent 的企业可信记忆治理参考实现。

[English README](README.md) · [治理控制台](docs/CONSOLE.md) · [MCP 与 OpenAI 接入](docs/INTEGRATIONS.md) · [DeepSeek 云端配置](docs/DEEPSEEK_API_CN.md) · [生产部署手册](docs/PRODUCTION_DEPLOYMENT.md) · [架构说明](docs/ARCHITECTURE.md) · [安全设计](docs/SECURITY.md) · [可观测性](docs/OBSERVABILITY.md) · [真实评测](docs/EVALUATION.md)

## 项目解决什么问题

普通 RAG 通常只回答“哪些文本与问题最相关”，但企业知识应用还必须回答：

- 一条聊天内容、会议纪要或模型推断，是否有资格写入长期记忆？
- 新旧制度冲突时，哪个版本在指定业务日期有效？
- 证据权威性不足或相互冲突时，系统能否拒答并留下审计记录？

TARCS-Mem 在知识写入、检索和生成之间增加可解释的治理层：

- **GuardWrite**：按来源、证据完整性、抽取置信度和长期价值决定激活、待审核或拒绝；
- **双时间与冲突治理**：同时记录业务生效时间与系统获知时间，保留被替代版本；
- **GuardRead / TARCS**：融合相关性、时效、权威、可靠性与上下文成本，再进行预算内 MMR 证据选择；
- **可信拒答**：没有合格证据时明确拒答，不把模型推断当事实；
- **人工审核闭环**：具名审核人可批准或驳回待审核记忆，备注和状态变化进入审计轨迹；低权威来源不能静默覆盖现行制度。
- **企业安全基线**：写入前凭证阻断、PII 脱敏、租户隔离、文档角色 ACL、数据分级和可选 Bearer 鉴权；查询审计不保存原始问题。
- **云端出境拦截**：云端模型调用前按已选证据分类强制校验，默认只允许 `public/internal`；机密与受限内容会拒绝出境，并留下不含正文的审计事件和指标。
- **生成引用校验**：模型输出必须引用受治理证据包里的准确 `[SOURCE: ...]` 标签；缺失或编造来源的回答会被拦截。
- **隐私安全的可观测性**：内置 Prometheus 文本指标、有限内存链路追踪、trace ID 和 P95 延迟统计，默认不采集问题、文档或密钥正文。
- **MCP v2 接入**：任意 MCP Host 可以检索可信记忆；Agent 提交的记忆被固定为低权威待审核声明，无法冒充正式制度自动激活。
- **OpenAI 兼容网关**：现有聊天客户端可以调用 `/v1/chat/completions`，同时保留时间、权限、引用和云端出境治理。
- **LangChain / LlamaIndex 一行式适配**：直接返回两个框架的原生 Retriever，且只能看到通过 GuardRead 的证据。
- **Confluence 真实增量同步**：基于 Confluence Cloud REST API v2，支持游标分页、版本与内容哈希检查点、确定性幂等 ID、安全删除确认和默认人工审核。
- **新手友好的治理控制台**：在一个页面体系中完成治理健康检查、安全问答演示、可信记忆查询、具名人工审核、隐私安全 Trace 和集成配置。

![TARCS-Mem 带来源与决策轨迹的可信回答](docs/demo/assets/02-answer-v07.jpg)

| 普通 RAG | TARCS-Mem |
| --- | --- |
| 抽取后直接写入文本 | 每条记忆进入激活、待审核或拒绝状态 |
| 只取最相似片段 | 排序前强制校验租户、角色、状态和业务时间 |
| 覆盖旧版本或忽略冲突 | 保留历史并解释新版本为何替代旧版本 |
| 仅提示模型添加引用 | 拦截缺失/编造引用和未授权云端出境 |

## 技术栈

Python · FastAPI · Qwen3 / Ollama · BGE · Qdrant · SQLite · Gradio · Docker · Pytest

核心治理算法不依赖模型或向量数据库；Qwen3、BGE 与 Qdrant 是可替换的本地适配器。

## 5 分钟运行治理控制台

需要 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'

tarcsmem seed --db ./data/tarcsmem-demo.db --if-empty
tarcsmem serve --db ./data/tarcsmem-demo.db --port 8000
```

浏览器打开 `http://127.0.0.1:8000/console/`。控制台与 FastAPI 使用同一服务，不需要单独运行前端。可以直接查看治理健康、安全测试场、可信记忆、人工审核、Trace 和集成状态。启用 `TARCSMEM_API_KEY` 后，在“集成中心 → 配置 API Key”填写令牌；令牌只保存在当前浏览器标签页。详细说明见 [治理控制台指南](docs/CONSOLE.md)。

原有 Gradio 对话演示仍可通过 `pip install -e '.[ui,dev]'` 和 `tarcsmem ui --db ./data/tarcsmem-demo.db` 启动，默认地址为 `http://127.0.0.1:7860`。它适合体验文档上传与本地/云端 Agent；v0.8 控制台更适合治理人员和试点演示。

## 接入已有 Agent 与聊天工具

作为 MCP v2 stdio 服务运行：

```bash
pip install -e '.[mcp]'
tarcsmem-mcp
```

也可以把 OpenAI 兼容客户端的 `base_url` 指向
`http://127.0.0.1:8000/v1`，模型填写 `tarcsmem-governed`。当前接口刻意不提供流式输出，确保完整答案先通过引用校验再返回。Host 配置、curl 示例和安全边界见 [集成指南](docs/INTEGRATIONS.md)。

已有 LangChain 或 LlamaIndex 项目可直接接入：

```python
from datetime import date
from tarcsmem import TARCSMemoryService, as_langchain_retriever, as_llamaindex_retriever

memory = TARCSMemoryService("./data/tarcsmem.db")
langchain_retriever = as_langchain_retriever(memory, date.today())
llamaindex_retriever = as_llamaindex_retriever(memory, date.today())
```

安装 `pip install -e '.[integrations]'`。两个适配器都不会把未通过权限、状态、业务时间和冲突治理的候选片段交给上层框架。

使用真实 Confluence Cloud 空间做增量同步：

```bash
export TARCSMEM_CONFLUENCE_BASE_URL=https://your-site.atlassian.net
export TARCSMEM_CONFLUENCE_EMAIL=you@example.com
export TARCSMEM_CONFLUENCE_SPACE_ID=123456
export TARCSMEM_CONFLUENCE_API_TOKEN='从密钥管理器读取'
tarcsmem sync-confluence --db ./data/tarcsmem.db
```

默认按 `meeting_note` 低权威来源导入并进入人工审核。只有当该空间本身已有正式发布审批流程时，才使用 `--source-type official_policy --authority 1.0`。完整边界见 [Confluence 增量同步说明](docs/INTEGRATIONS.md#confluence-cloud-incremental-sync)。

## 不运行本地大模型：使用 DeepSeek API

先撤销任何曾发送到聊天、截图或日志中的密钥，并在 DeepSeek 控制台生成新密钥。密钥只能保存在本机环境变量或被 `.gitignore` 排除的 `.env` 中：

```bash
pip install -e '.[ui,dev,api,cloud]'
cp .env.example .env
# 在 .env 中把 TARCSMEM_LLM_PROVIDER 改为 deepseek，并填写新密钥：
# DEEPSEEK_API_KEY=你的新密钥

set -a
source .env
set +a

export TARCSMEM_EMBEDDING_BACKEND=hash
export TARCSMEM_RERANKER=off
tarcsmem ui --db ./data/tarcsmem-deepseek.db
```

默认使用 `deepseek-v4-flash` 非思考模式；可通过 `TARCSMEM_DEEPSEEK_MODEL=deepseek-v4-pro` 切换。启用云端生成时，经过权限与时间治理后选出的证据会发送给 DeepSeek。系统默认强制只允许 `public,internal` 分类出境；`confidential/restricted` 会在调用前被拦截，只有安全负责人显式调整 `TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS` 后才会放行。完整参数、安全边界和故障排查见 [DeepSeek 云端配置](docs/DEEPSEEK_API_CN.md)。

## 测试与评估

```bash
pip install -e '.[dev,api]'
pytest -q
tarcsmem seed --db ./data/tarcsmem.db
tarcsmem evaluate --db ./data/tarcsmem.db
tarcsmem evaluate-public --queries 120 --distractors 300 \
  --output docs/benchmarks/fiqa-public-report.json
```

当前自动化测试共 **92 项**，覆盖治理、安全、ACL、API、控制台鉴权边界、MCP v2 协议、OpenAI 兼容接口、LangChain/LlamaIndex 原生调用、Confluence 增量同步、DeepSeek 云端适配、零配置渲染、云端出境拦截、生成引用校验、限流、幂等写入、检索回归、可观测性和评测代码。CI 同时验证 React/TypeScript 生产构建、Python 3.11/3.12、可选依赖、Docker 构建，并从 wheel 在全新环境中执行 CLI 冒烟测试。真实公开 FiQA test/qrels 评测现已扩展至 **120 个查询、610 个候选文档**，并比较词法、哈希语义、RRF 和完整 TARCS 四组消融。TARCS 的 Recall@10 为 **0.4446**、MRR@10 为 **0.4839**、NDCG@10 为 **0.3783**；词法基线分别为 0.3624、0.3748 和 0.2988。每项指标附带1000次bootstrap的95%置信区间。该实验仍是有限候选池，不能与完整57.6k文档的BEIR榜单横向比较。详见 [docs/EVALUATION.md](docs/EVALUATION.md)。

经验证的 85 秒 v0.7 中文演示视频和逐秒脚本见 [docs/demo](docs/demo/)。

## 项目结构

```text
src/tarcsmem/       核心治理、检索、Agent、API 与 UI
console/            React / TypeScript 治理控制台源码
tests/              单元测试与治理工作流测试
docs/               架构、算法、数据集、安全与运行说明
examples/           可复制的 MCP 与 OpenAI 兼容接入示例
.github/workflows/  GitHub Actions 持续集成
```

## 安全边界

这是作品集 / 开源 Alpha 参考实现，不是已通过企业生产认证的产品。仓库已实现确定性的安全基线，但请求体里的角色仅用于本地演示，不能代替可信身份声明。生产环境仍需由 OIDC/SSO 注入不可伪造的租户和角色，接入 Casbin/OPA、企业 DLP/Presidio、KMS、恶意文件扫描、限流、备份恢复、SIEM 和保留/删除流程。可按 [生产部署手册](docs/PRODUCTION_DEPLOYMENT.md) 从受控试点推进。

## 许可证

MIT。
