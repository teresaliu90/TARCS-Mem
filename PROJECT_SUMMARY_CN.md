# TARCS-Mem 项目说明

## 这是什么

TARCS-Mem 是一个“企业可信记忆治理”开源参考实现。它不试图做功能最全的聊天机器人，而是解决企业知识 Agent 最危险的三个问题：

1. 聊天记录、会议纪要或模型推断能不能自动写入长期记忆？
2. 新旧制度冲突时，系统应该信谁、使用哪个有效时间版本？
3. 证据不足时，系统能否明确拒答而不是编造？

## 核心机制

- **GuardWrite**：按来源权威、证据、置信度和持久价值决定记忆进入 `active / pending / rejected`；模型推断不能直接成为事实。
- **双时间记忆**：区别业务生效时间和系统获知时间，支持查询历史制度版本。
- **TARCS 检索**：在相关性以外，同时考虑时效、权威、证据可靠性和 token 成本；在预算内选择多样化证据。
- **可追溯**：所有写入、状态变更和版本覆盖都有审计事件。
- **企业安全基线**：凭证阻断、PII 脱敏、租户隔离、文档角色 ACL、数据分级与 API Bearer 鉴权。
- **可观测性**：Prometheus 指标、trace ID、P95 延迟和有限内存 span；不记录原始问题或文档正文。
- **真实公开评测**：120条FiQA test/qrels、610篇候选文档、4组消融、1000次bootstrap置信区间和延迟报告。

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'
tarcsmem seed --db ./data/tarcsmem.db
tarcsmem evaluate --db ./data/tarcsmem.db
tarcsmem evaluate-public --output docs/benchmarks/fiqa-public-report.json
tarcsmem serve --db ./data/tarcsmem.db
```

浏览器打开 `http://127.0.0.1:8000/console/` 使用 v0.8 治理控制台。旧版演示视频保留在 `docs/demo/` 作为历史材料；推送与 `pyproject.toml` 版本一致的标签后，Release 工作流会自动测试、构建 Python 包并附加评测资产。

访问 `http://127.0.0.1:8000/docs` 查看 API。

## 重要边界

这是可运行的作品集/开源 Alpha，而非可直接投入真实企业生产的完整系统。Qwen3/BGE/Qdrant、本地人工审核、安全与观测基线已经具备；真实上线仍需 OIDC/SSO 可信身份、Casbin/OPA、企业 DLP/KMS、恶意文件扫描、分布式追踪、备份恢复和真实业务标注集。

内置数据全部为虚构合成数据，不含任何客户、雇主或内部资料。
