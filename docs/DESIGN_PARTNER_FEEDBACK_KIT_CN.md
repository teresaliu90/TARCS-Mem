# TARCS-Mem 企业工程师反馈与匿名试点执行包

> 当前状态：**工具和流程已准备，尚不代表已经获得反馈、客户、试点或采用。**

这份执行包用于完成两个可验证里程碑：

1. 让 3～5 位企业 AI / RAG / 平台 / 安全工程师独立运行 TARCS-Mem，并留下可引用的结构化反馈；
2. 与其中一位合适的 Design Partner 完成一个边界明确、可匿名公开的试点案例。

不要把一般聊天、点赞或只看截图算作“工程师反馈”。合格反馈至少需要参与者完成一次运行，或基于代码/架构进行具体评审，并明确指出一个有价值之处和一个阻碍采用的问题。

## 一次只做的下一步

先邀请 **5 人**，目标是获得 **3 次实际体验**。不要先批量联系几十人。

执行顺序：

- [ ] 选出 5 位与企业 RAG、Agent、知识平台或 AI 安全相关的工程师；
- [ ] 分别发送下方短邀请，不群发；
- [ ] 为愿意参加的人安排 30 分钟；
- [ ] 让对方共享屏幕完成 10 分钟任务，维护者只观察、不代操作；
- [ ] 访谈后 24 小时内记录反馈，并请求对方确认摘要是否准确；
- [ ] 将可公开、无敏感信息的问题转成 GitHub Issue；
- [ ] 满足试点准入条件后，再邀请一位进入 2～4 周匿名试点。

## 目标参与者

优先寻找直接面对下列问题的人：

- 企业 RAG / Agent 工程师：做知识检索、引用、工具调用或 Agent memory；
- AI 平台工程师：负责权限、租户隔离、模型网关、可观测性或部署；
- 知识平台工程师：维护 Confluence、SharePoint、Notion 或内部 Wiki；
- AI 安全 / 合规工程师：关注数据分级、出境、审计和访问控制；
- 解决方案架构师：需要为企业客户解释“这次回答为什么可信”。

不要求参与者代表公司正式采购，也不要求提供公司数据。

## 可直接发送的邀请话术

### 私信短版

```text
你好，我在做一个 MIT 开源项目 TARCS-Mem，为企业 RAG / AI Agent 增加权限、时效、冲突、引用和回答审计治理。

我正在找 3～5 位企业 AI 工程师做一次 30 分钟、无销售的可用性评审：你会用合成数据独立跑一个 10 分钟任务，我只观察哪里看不懂或跑不通。不会要求你上传公司数据，也不会公开姓名或公司，除非你书面同意。

仓库：https://github.com/teresaliu90/TARCS-Mem
如果方向与你的工作相关，愿意帮我做一次真实评审吗？作为回报，我会整理问题、公开修复，并把改进结果发给你确认。
```

### GitHub / 社区帖子版

```text
Looking for 3–5 enterprise AI engineers to review TARCS-Mem

TARCS-Mem is an MIT-licensed governance layer for enterprise RAG and AI agents. It focuses on write admission, temporal/version conflicts, ACL-aware retrieval, citation verification and answer-centric evidence trails.

The review takes 30 minutes and uses synthetic data only. The core task is to clone the repo, produce a governed answer, and inspect why each piece of evidence was selected or excluded. This is a usability and architecture review, not a sales call.

No company data is required. Notes remain anonymous unless the participant explicitly approves attribution. If this relates to your work, please reply or open a Discussion.
```

## 10 分钟首次运行任务

把这一段原样交给参与者。不要提前解释按钮在哪里；观察 README 和界面能否自己完成引导。

### 给参与者的任务

```text
目标：在 10 分钟内，用合成数据获得一条受治理回答，并说明它为什么可以返回。

1. 按 README 的 “5 分钟运行治理控制台” 启动项目。
2. 打开控制台，运行默认“制度版本”场景。
3. 找到这次查询的回答 ID。
4. 打开回答证据链，找出：
   - 采用了哪条来源；
   - 至少一个证据被排除的原因；
   - 使用了哪个策略版本；
   - 引用验证是否通过；
   - 当前审计存储为什么不能声称“防篡改”。
5. 用一句话回答：你会把 TARCS-Mem 放在现有 RAG/Agent 架构的哪个位置？

请在遇到不确定时直接说出来，不需要猜，也不要担心“操作错”。
```

### 观察者记录

| 指标 | 记录方式 | 成功标准 |
| --- | --- | --- |
| 启动成功 | 从开始计时到控制台可用 | ≤ 5 分钟 |
| 首次结果 | 从打开控制台到返回回答 | ≤ 3 分钟 |
| 找到证据链 | 从回答出现到打开 Evidence Chain | ≤ 1 分钟 |
| 理解程度 | 正确回答任务中的 5 个问题 | ≥ 4/5 |
| 求助次数 | 维护者必须介入的次数 | ≤ 1 次 |
| 严重阻塞 | 安装失败、按钮不可见、术语无法理解 | 0 个未记录问题 |

记录操作事实，不评价参与者能力。例如写“在 README 中寻找启动命令 90 秒”，不要写“用户不熟悉 Python”。

## 30 分钟工程师访谈脚本

### 0～3 分钟：边界和背景

- 简要说明这是开源可用性/架构评审，不是销售或招聘。
- 确认只使用合成数据，不输入公司名称、客户名、密钥、内部 URL 或文档。
- 询问其工作类别和使用过的 RAG / Agent 技术，不记录雇主敏感信息。

### 3～15 分钟：独立任务

- 发送上方 10 分钟任务。
- 请参与者边操作边说出预期。
- 除非完全阻塞，不提供提示；所有阻塞点都计入记录。

### 15～25 分钟：核心问题

按顺序询问：

1. 你用一句话怎么描述这个项目？
2. 哪个功能对真实企业 RAG / Agent 最有价值？为什么？
3. 哪个概念、页面或安装步骤最难理解？
4. 证据链里还缺少什么，才足以支持你调试或审计一次回答？
5. 你最担心的安全或数据边界是什么？
6. 如果接入你熟悉的系统，最先需要哪个连接器或 SDK？
7. 哪个缺口会让你不能开始一个小型试点？
8. 你愿意提交 Issue、PR，还是只愿意继续给反馈？任何答案都可以。

### 25～30 分钟：评分与许可

请参与者给出 1～5 分：

- 价值主张清晰度；
- 10 分钟上手难度（5 = 很容易）；
- 证据链可理解性；
- 与现有技术栈的集成可行性；
- 启动匿名试点的意愿。

最后确认三件事：

- 哪些反馈可以匿名公开；
- 是否允许将问题转成公开 GitHub Issue；
- 是否愿意在修复后做一次 15 分钟复测。

## 结构化反馈表

每位参与者复制一份，使用 `R01`、`R02` 等匿名编号。原始联系方式不要提交到 Git 仓库。

```markdown
# TARCS-Mem feedback — R01

- Date:
- Role category: RAG / Agent / Platform / Knowledge / Security / Other
- Review type: hands-on / code review / architecture review
- Consent: private only / anonymous aggregate / attributed (written approval attached)
- Repository commit tested:
- Environment: OS, Python, Docker/non-Docker

## Task evidence
- Console started in: __ minutes
- Governed answer produced: yes / no
- Evidence chain opened: yes / no
- Task questions correct: __ / 5
- Maintainer interventions: __

## Scores (1–5)
- Value clarity:
- First-run ease:
- Evidence-chain clarity:
- Integration feasibility:
- Pilot interest:

## Most valuable

## Adoption blocker

## Missing evidence/audit field

## Requested connector or SDK

## Security concern

## Verbatim quote (publish only if consent allows)

## Follow-up
- Public issue allowed: yes / no
- Retest agreed: yes / no
- Pilot discussion agreed: yes / no
```

## 如何计算“已获得 3～5 位真实反馈”

只有同时满足以下条件才计数：

- 是目标角色之一，且与企业 AI 系统有直接工程经验；
- 完成 hands-on 任务，或完成有具体代码/架构意见的技术评审；
- 留下结构化记录；
- 至少给出一个具体价值点和一个具体缺口；
- 反馈公开范围已经确认。

在 README 或公开文章中只能写事实，例如“4 位工程师完成了测试，其中 3 位在 10 分钟内打开证据链”。不要把受访者称为客户，也不要公开公司名，除非获得书面授权。

## 匿名试点准入条件

候选试点必须同时具备：

- 一个明确、低风险的政策问答或内部知识检索场景；
- 一位业务/知识负责人和一位技术负责人；
- 50～500 份边界清晰、允许用于试点的文档，或完全合成的等价数据集；
- 明确的角色、租户、数据分级和业务生效时间规则；
- 20～50 个由领域负责人确认的评估问题；
- 可以在隔离环境运行，且模型出境范围得到书面确认；
- 双方同意退出、删除和案例公开边界。

以下情况不进入试点：医疗诊断、信贷/招聘自动决策、未经批准的个人敏感数据、无法明确数据所有权、要求把 Early Alpha 直接作为生产安全控制。

## 2～4 周试点流程

### 第 0 阶段：书面范围（开始前）

- 确认数据所有者、处理位置、允许的模型、保留期限和删除方式；
- 固定试点版本、配置和评估集；
- 记录基线系统或人工流程的结果；
- 签署适合双方的保密/数据处理文件；本模板不是法律意见。

### 第 1 阶段：合成或脱敏数据验证

- 验证连接器、字段映射、GuardWrite 状态和冲突规则；
- 人工检查 10 条写入决策和 10 条拒答/排除决策；
- 未通过前不接入真实内部文档。

### 第 2 阶段：有限真实数据

- 只接入批准的数据集和测试用户；
- 运行冻结评估集，记录每个回答 ID 和审计链；
- 每周与负责人复核误答、误拒答、ACL 拒绝和出境拦截。

### 第 3 阶段：结论与清理

- 对比基线与成功指标；
- 输出继续、修改后继续或停止的明确结论；
- 按约定删除数据、密钥和临时环境；
- 由对方审批匿名案例中的每一项可公开信息。

## 建议的试点成功指标

开始前为每个指标填写目标，不要事后选择对项目有利的数字。

| 类别 | 指标 | 示例目标 |
| --- | --- | --- |
| 可用性 | 首次运行完成率 | ≥ 80% 无维护者代操作 |
| 上手 | 中位数首次证据链时间 | ≤ 10 分钟 |
| 检索 | Recall@k / MRR / 领域问题命中率 | 不低于已声明基线 |
| 可信回答 | 引用全部属于证据包 | 100% |
| 权限 | 未授权证据进入回答 | 0 次 |
| 时效 | 使用已失效/被替代制度 | 0 次 |
| 拒答 | 应拒答问题正确拒答率 | 预先约定，如 ≥ 90% |
| 审计 | 抽样回答可重建证据链 | 100% |
| 出境 | 未经批准的数据出境 | 0 次 |
| 性能 | P95 查询延迟 | 按部署环境预先约定 |

结果必须同时报告样本量、失败案例和限制。试点成功不等于生产认证。

## 数据、同意与公开边界

- 默认只收集匿名编号、角色类别、环境、计时、评分和产品反馈。
- 不把姓名、邮箱、公司、内部 URL、截图、日志或数据提交到公开仓库。
- 录音、录屏、逐字引用和公司归属都需要单独、明确的书面同意。
- 参与者可要求删除原始反馈；删除负责人和期限应在访谈前说明。
- 公开 GitHub Issue 前移除身份、架构拓扑、域名、数据样本和安全弱点细节。
- 安全漏洞按照 `SECURITY.md` 私下报告，不放入公开 Issue。
- 匿名案例必须由 Design Partner 在发布前逐段确认。

## 匿名试点案例模板

```markdown
# An anonymized TARCS-Mem design-partner pilot

Status: completed / stopped / in progress
Pilot dates:
TARCS-Mem commit/version:

## Participant profile
- Industry category: (only if approved)
- Team type: enterprise AI / platform / knowledge / security
- Deployment boundary: local / private cloud / other approved description

## Problem
- Existing workflow:
- Specific governance risk:
- Why ordinary retrieval was insufficient:

## Scope
- Document count and approved data classes:
- Number of evaluation questions:
- Roles/tenants represented:
- Explicitly out of scope:

## Configuration
- Ingestion source and connector:
- Retrieval/generation mode:
- GuardWrite/GuardRead policies:
- Identity and audit-store limitations:

## Pre-registered success criteria
| Metric | Target | Result |
| --- | --- | --- |

## Results
- What worked:
- What failed:
- Correct abstentions:
- ACL/time/conflict findings:
- Performance:

## Product changes caused by the pilot
- Issue/PR links:

## Limitations
- Why this result does not prove production readiness:
- Remaining security, identity, scale or evaluation gaps:

## Participant-approved quote
(Omit unless written permission exists.)

## Publication approval
- Approved by anonymous partner on:
- Allowed attribution level:
```

## 反馈转 GitHub Issue 的规则

每个问题只建立一个可验收 Issue，包含：

- 观察到的行为，而不是对参与者的评价；
- 可复现环境和仓库 commit；
- 预期行为与实际行为；
- 验收标准；
- 隐私处理说明；
- 合适的 `feedback`, `ui/ux`, `docs`, `integration` 或 `security` label。

对外可以准确写“反馈招募已开始”“试点流程已准备”。只有完成并保留上述证据后，才能写“已获得 3～5 位工程师反馈”或“已完成一个匿名试点”。
