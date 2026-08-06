# 第一次把 TARCS-Mem 上传到 GitHub

这份步骤只上传源码、测试和公开说明。`.gitignore` 已排除虚拟环境、本地数据库、Qdrant 索引、临时文件、压缩包与 `.env`。

## 1. 注册并确认 GitHub 信息

1. 注册或登录 GitHub。
2. 记下用户名。
3. 在 GitHub 的邮箱设置中决定：使用公开邮箱，或使用 GitHub 提供的 `noreply` 邮箱。

## 2. 在 GitHub 创建空仓库

1. 点击右上角 `+`，选择 `New repository`。
2. 仓库名建议使用 `TARCS-Mem`。
3. 选择 `Public`（作品集）或 `Private`（暂不公开）。
4. **不要**勾选自动创建 README、`.gitignore` 或 License，因为本地已经有这些文件。
5. 点击 `Create repository`，暂时保留页面。

## 3. 在项目目录初始化本地仓库

把尖括号内容换成你自己的信息：

```bash
cd /你的路径/TARCS-Mem
git config user.name "<你的 GitHub 用户名>"
git config user.email "<你的 GitHub 邮箱或 noreply 邮箱>"
git init -b main
git status
```

## 4. 首次提交前检查

```bash
git status --short
git diff --check
git add .
git status --short
```

确认列表中没有 `.env`、数据库、个人简历、公司文件、模型文件或密钥。若发现不应公开的文件，先执行 `git restore --staged <文件路径>`，再更新 `.gitignore`。

确认无误后提交：

```bash
git commit -m "feat: publish TARCS-Mem trusted memory governance demo"
```

## 5. 连接 GitHub 并推送

在 GitHub 新仓库页面复制 HTTPS 地址，然后执行：

```bash
git remote add origin https://github.com/<你的用户名>/TARCS-Mem.git
git remote -v
git push -u origin main
```

GitHub 不接受账户密码作为 Git 推送密码。如果终端要求认证，按浏览器提示登录，或使用 Personal Access Token。不要把 token 写进命令、README、`.env.example` 或聊天截图。

## 6. 上传后验证

在 GitHub 仓库页面检查：

- README 首页能正常显示；
- `Actions` 中 CI 通过；
- 仓库没有数据库、`.env`、简历原图或压缩包；
- `About` 中可填写描述：`Trusted enterprise memory governance for RAG and AI agents`；
- Topics 可填写：`rag`、`ai-agent`、`memory`、`governance`、`enterprise-ai`、`mcp`、`openai-compatible`、`qdrant`、`fastapi`。
- 设置 `Social preview`，优先使用展示回答、来源、业务时间和 TARCS 分数的界面图。
- 开启 `Discussions`，建立 `Show and tell`、`Ideas`、`Q&A` 三个分类，降低首次贡献门槛。
- 在第一个 Release 中附加 wheel、FiQA 报告、校验和与演示视频。

## 7. 冲击首批 Star 的发布顺序

1. 先确认 CI 全绿，再创建 `v0.7.0` Release，避免访问者第一天遇到红色构建。
2. README 首屏只讲一个定位：企业 Agent 的可信记忆治理层，不宣传成另一个通用聊天机器人。
3. 用一张对比图展示普通 RAG 与 TARCS-Mem 在过期制度、冲突、越权和证据不足时的差异。
4. 发布一段不超过90秒的 v0.7 演示，前三十秒展示零配置启动和一次可追溯回答。
5. 准备三个可复制场景：MCP Host、OpenAI 兼容客户端、原生企业治理 API。
6. 每个公开介绍都如实注明 FiQA 是有限候选池评测，并直接链接可复现报告。

## 以后更新代码

```bash
git status
git add .
git commit -m "fix: 简短说明这次改了什么"
git push
```

提交信息推荐用英文类型 + 简短说明：`feat:` 新功能、`fix:` 修复、`docs:` 文档、`test:` 测试、`refactor:` 重构。

GitHub 官方参考：[上传本地代码](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github) · [设置提交邮箱](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address?platform=mac) · [命令行认证](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)
