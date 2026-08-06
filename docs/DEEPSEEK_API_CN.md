# 使用 DeepSeek 云端 API

TARCS-Mem 支持在不运行 Ollama/Qwen3 的情况下，把经过 GuardRead、时间有效性、权限和 TARCS 证据选择后的上下文发送给 DeepSeek，再生成带引用的回答。

## 安全第一

任何曾经出现在聊天、截图、邮件、终端共享记录或 Git 历史里的 API Key 都应视为已泄露。请先在 DeepSeek 控制台撤销，再生成新密钥。

- 不要把密钥发给任何人，也不要粘贴到 issue、README 或演示视频。
- 不要修改 `.env.example` 填入真实值。
- `.env` 已被仓库的 `.gitignore` 排除；提交前仍应运行密钥扫描。
- 云端模式会把最终选中的证据片段和问题发送给 DeepSeek。只有获得授权的数据才能使用云端模型。
- 调用前会强制执行分类出境策略：默认仅 `public,internal` 可发送；`confidential,restricted` 会阻断本次生成，不会请求 DeepSeek。
- TARCS-Mem 不会把密钥放进请求正文、指标、错误信息或审计日志。

## 1. 安装轻量依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[ui,dev,api,cloud]'
```

DeepSeek 客户端使用 Python 标准库，不需要安装 OpenAI SDK。

## 2. 创建本机配置

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
TARCSMEM_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=在控制台重新生成的密钥
TARCSMEM_DEEPSEEK_BASE_URL=https://api.deepseek.com
TARCSMEM_DEEPSEEK_MODEL=deepseek-v4-flash
TARCSMEM_DEEPSEEK_THINKING=false
TARCSMEM_DEEPSEEK_TIMEOUT=90
TARCSMEM_DEEPSEEK_MAX_RETRIES=2
TARCSMEM_DEEPSEEK_MAX_TOKENS=1024

# 云端出境白名单；变更必须经过安全负责人审批。
TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS=public,internal

# 不使用本地 BGE 时启用轻量检索：
TARCSMEM_EMBEDDING_BACKEND=hash
TARCSMEM_RERANKER=off
```

官方在 2026 年 8 月提供的模型名为 `deepseek-v4-flash` 和 `deepseek-v4-pro`。旧的 `deepseek-chat`、`deepseek-reasoner` 已在 2026-07-24 停用，因此适配器会拒绝这些旧名称。

## 3. 加载配置并启动

macOS/Linux：

```bash
set -a
source .env
set +a
tarcsmem ui --db ./data/tarcsmem-deepseek.db
```

浏览器打开 `http://127.0.0.1:7860`。页面顶部应显示：

```text
回答模型：DeepSeek API（云端） · deepseek-v4-flash
安全模式：证据会发送至云端模型
```

Windows PowerShell 可在当前窗口逐项设置，不要把含真实密钥的脚本提交到 Git：

```powershell
$env:TARCSMEM_LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="在控制台重新生成的密钥"
$env:TARCSMEM_DEEPSEEK_MODEL="deepseek-v4-flash"
$env:TARCSMEM_EMBEDDING_BACKEND="hash"
$env:TARCSMEM_RERANKER="off"
tarcsmem ui --db ./data/tarcsmem-deepseek.db
```

## 4. 模型选择

| 模型 | 建议用途 |
|---|---|
| `deepseek-v4-flash` | 默认；成本和延迟更适合普通企业问答 |
| `deepseek-v4-pro` | 更复杂的综合分析；成本和延迟通常更高 |

RAG 默认设置 `TARCSMEM_DEEPSEEK_THINKING=false`。如确实需要复杂推理，可改为 `true`；这会使用更多推理 token，并可能显著增加延迟与费用。

## 5. 验证但不产生 API 费用

```bash
pytest -q tests/test_deepseek.py
```

测试使用本地 mock，不会调用 DeepSeek，也不会产生费用。确认新密钥已经在当前终端加载后，再通过 UI 发起一条真实问题完成端到端验证。

若看到“未调用云端模型”的拒答，说明选中证据的分类不在 `TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS` 内。这是预期的防泄露行为。请改用本地模型，或由安全负责人按数据分类、供应商、区域与保留条款完成审批后再修改白名单；不要为了通过一次问答直接放开 `restricted`。

## 6. 常见错误

- `requires DEEPSEEK_API_KEY`：当前进程没有读取到密钥，重新执行 `source .env`。
- `authentication failed`：密钥无效或已撤销；生成新密钥，不要继续使用泄露的密钥。
- `balance is insufficient`：检查 DeepSeek 账户余额。
- `rate limit exceeded`：稍后重试或减少并发。
- `Cannot reach`：检查网络、代理和 `TARCSMEM_DEEPSEEK_BASE_URL`。Python.org 的 macOS Python 若报告证书链错误，请安装 `.[cloud]`；企业代理可通过 `TARCSMEM_CA_BUNDLE=/path/to/company-ca.pem` 指定可信 CA。实现始终验证 TLS，不提供跳过证书验证的开关。

接口实现遵循 DeepSeek 官方 OpenAI-compatible Chat Completions API：`POST https://api.deepseek.com/chat/completions`。
