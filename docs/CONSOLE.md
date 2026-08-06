# TARCS-Mem v0.8 治理控制台

治理控制台面向第一次接触企业 RAG 治理的工程师、产品负责人、知识管理员和安全审核人。它不要求用户先理解 TARCS、RRF 或 MMR，而是先回答三个业务问题：当前知识是否可信、什么需要人工处理、一次回答为什么被允许或拒绝。

## 启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'
tarcsmem seed --db ./data/tarcsmem-demo.db --if-empty
tarcsmem serve --db ./data/tarcsmem-demo.db --port 8000
```

打开 <http://127.0.0.1:8000/console/>。编译后的控制台已经包含在 Python 包中，与 API 同源运行，不需要额外启动 Node 服务。

## 10 分钟第一次体验

首页的引导进度只保存在当前浏览器会话，用来帮助新用户完成一条真实、可重复的治理路径：

1. **确认演示记忆**：种子数据包含 6 条合成记录，不含企业或个人真实数据。
2. **运行制度版本场景**：进入“安全测试场”，保留默认问题和业务日期，点击“查证并解释”。结果会显示稳定的回答 ID 和被选证据。
3. **打开回答证据链**：点击“查看回答证据链”，检查采用证据、排除原因摘要、策略版本、验证结果、写入/替代/审批沿袭、证据包 ID 和 Trace ID。

证据链不显示问题正文或文档正文。它会明确提示参考 SQLite 存储的
`chain_verified` 为 `false`；这表示事件可追溯，但尚未具备 WORM、哈希链或签名提供的
不可篡改证明。完成三步后仍可随时重新运行，进度不是权限或合规状态。

## 六个工作区

| 工作区 | 适合完成的任务 |
| --- | --- |
| 治理总览 | 查看可信记忆、待审核、冲突、即将失效和数据分级 |
| 安全测试场 | 用示例问题观察状态、时间、冲突和引用规则如何影响回答 |
| 可信记忆 | 搜索事实，查看来源、版本、访问范围和审计事件 |
| 审核工作台 | 由具名审核人批准或驳回候选信息，并记录依据 |
| Trace 与审计 | 查看不含问题正文和文档正文的执行状态与聚合指标 |
| 集成中心 | 查看 Agent、模型、数据源、向量库和框架的连接状态 |

## API 鉴权

生产或受控试点建议设置 `TARCSMEM_API_KEY`：

```bash
export TARCSMEM_API_KEY='从企业密钥管理器读取'
tarcsmem serve --db ./data/tarcsmem-demo.db --port 8000
```

静态控制台可以公开加载，但所有治理数据接口仍要求有效 Bearer Token。在“集成中心 → 配置 API Key”输入令牌后，它只保存在当前标签页的 `sessionStorage`，不会进入 URL、服务端数据库或 Trace。关闭标签页会自动清除。

回答证据链调用 `GET /v1/answers/{answer_id}/audit`。API 会重新校验租户和当前记录 ACL；
格式错误、不存在和无权查看的回答统一返回 `404`，避免泄露跨租户对象是否存在。
安全测试场的回答卡片和“Trace 与审计”中的回答级 Trace 都可以打开同一份证据链，
不会在前端另外拼接一套审计结构。

## 合成数据界面对比

v0.7 的回答页已经显示来源，但没有回答级的聚合证据链：

![v0.7 回答页](demo/assets/02-answer-v07.jpg)

v0.8 在相同的合成制度场景中增加回答 ID、排除摘要、策略/验证状态，以及
写入、版本替代和人工审批沿袭：

![v0.8 Answer Evidence Chain](demo/assets/05-answer-evidence-chain-v08.jpg)

当前版本已人工验证 320px 宽度下无横向溢出；提交前仍需运行 TypeScript 类型检查和生产构建。

## 前端开发

只有修改控制台源码时才需要 Node.js 22：

```bash
cd console
npm ci
npm run typecheck
npm run build
```

生产文件输出到 `src/tarcsmem/console_dist/`。提交前应同时提交控制台源码、`package-lock.json` 和编译产物，CI 会重新构建并检查产物是否一致。

## 试点边界

控制台中的 `tenant_id` 和角色仍是本地演示输入，不是可信身份。企业试点应在入口网关接入 OIDC/SSO，由服务端注入租户和角色；不要相信浏览器提交的角色声明。回答证据链也遵守这条边界，当前 API 查询参数不能替代可信身份。进一步要求见 [生产部署手册](PRODUCTION_DEPLOYMENT.md)。
