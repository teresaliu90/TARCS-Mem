# TARCS-Mem v0.8 合成试点报告

> **证据级别：维护者运行的合成验证（2026-08-07）。** 这不是客户试点，不代表企业采用，
> 没有包含外部 AI 工程师反馈，也不能替代生产安全评审。全部名称、制度、文档和结果均为
> 仓库内虚构 fixture。

## 1. 试点目标

验证一个新用户能否在无模型密钥、无外部数据源、无向量数据库的情况下，完成以下闭环：

1. 新旧制度进入同一冲突域，但旧版本不被覆盖；
2. 查询按业务日期选择当时有效的正式制度；
3. 未批准的会议纪要或员工陈述不能成为答案；
4. 已审批的限时例外能在有效期内被引用；
5. 证据不足时明确拒答；
6. 回答可通过 answer ID 追溯到证据、策略、写入事件与验证结果；
7. 另一租户或无角色用户不能读取记录、审计元数据或被过滤候选的数量。

## 2. 范围和数据

- 运行者：项目维护者；没有外部观察员。
- 数据：6 条合成记录，包括销售折扣新旧制度、未批准会议纪要、差旅制度、已审批展会
  例外和未验证员工陈述。
- 功能范围：GuardWrite、版本/冲突、业务时间、GuardRead/TARCS、拒答、引用、Answer
  Audit、Record Audit、租户/角色边界、FastAPI Console、TypeScript 客户端。
- 不在范围：真实 SSO、生产多租户身份、HA、不可篡改账本、真实客户文档、真实并发负载。

## 3. 预注册验收标准

| 指标 | 通过标准 |
| --- | ---: |
| 4 个治理用例正确结果与来源 | 4 / 4 |
| 应拒答用例 | 1 / 1 正确拒答 |
| 新制度查询 | 必须引用 `POLICY-SALES-2026-07#1` |
| 历史日期查询 | 必须引用 `POLICY-SALES-2026-01#1` |
| 跨租户未知/无权 ID | 相同 404，不暴露 source ref、actor 或排除计数 |
| Quickstart | 10 分钟内，无外部凭证或模型下载 |
| 审计完整性声明 | SQLite 必须显示 `chain_verified: false` |

## 4. 结果

| 结果 | TARCS-Mem | 朴素词法基线 |
| --- | ---: | ---: |
| 4 个用例总体正确率 | **100% (4/4)** | 25% (1/4) |
| 预期拒答正确率 | **100% (1/1)** | 0% (0/1) |
| 平均采用证据数 | 0.75 | 未记录 |
| 平均估算上下文 token | 15.75 | 未记录 |

TARCS-Mem 在当前小型 fixture 中正确处理了新版本、历史版本、已审批例外和未验证陈述。
朴素词法基线在新旧版本和未验证陈述场景中选择了错误来源。该对比只证明规则在这 4 个
预定义案例中生效，不证明开放域检索质量或真实企业 ROI。

端到端脚本还验证了：Console 可加载、`sales-v2` 被选中、待审核会议纪要未进入证据包、
引用和 Trace ID 存在、Answer Audit 与 Record Audit 可读、TypeScript 客户端可处理
`answered/abstained` 和 HTTP 错误。租户隔离对抗测试覆盖了空角色、错误租户、重复 ID、
审计角色、Qdrant 源头过滤与归一化后重检、连接器 checkpoint 租户绑定。

机器可读结果见
[`docs/benchmarks/synthetic-pilot-report.json`](benchmarks/synthetic-pilot-report.json)。

## 5. 复现

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'

tarcsmem evaluate --db /tmp/tarcsmem-synthetic-pilot.db
pytest -q tests/test_tenant_isolation_contract.py
TARCSMEM_RUN_TYPESCRIPT_SMOKE=1 ./scripts/verify_quickstart.sh
```

## 6. 失败、限制和下一步

- 样本只有 4 个问答用例；100% 不可外推到真实企业数据。
- 结果由维护者自己运行，没有盲测、独立复核或领域专家判分。
- SQLite 审计事件可追溯但不具备不可篡改证明，报告不宣称 hash chain 已验证。
- 请求里的租户和角色是演示输入；生产必须由 OIDC/SSO 在可信边界注入。
- 没有测真实 Confluence 权限变化、长期 checkpoint 恢复、并发审核、灾备或容量上限。

下一阶段不应伪造“真实试点”，而应邀请 3～5 位企业 AI 工程师按同一验收表独立运行，
记录成功时间、困惑点、失败日志和建议；之后再与一个获得授权的 Design Partner 使用匿名化
或合成业务规则完成受控试点，并由对方确认可公开的结论。
