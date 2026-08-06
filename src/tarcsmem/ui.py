"""Gradio UI for a local, inspectable TARCS-Mem Agent demonstration."""

from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime

from .agent import LocalAgentConfig, TARCSChatAgent
from .models import SourceType

SOURCE_LABELS = {
    SourceType.OFFICIAL_POLICY: "正式制度 / 官方文件",
    SourceType.APPROVED_EXCEPTION: "已审批例外",
    SourceType.MEETING_NOTE: "会议纪要",
    SourceType.USER_CLAIM: "用户陈述 / 待核实",
    SourceType.MODEL_INFERENCE: "模型推断（禁止写入事实）",
    SourceType.SYSTEM_RECORD: "系统记录",
    SourceType.PUBLIC_DATASET: "公开数据集",
}


def resolve_business_date(question: str, fallback: date | None = None) -> tuple[date, str]:
    """Infer a business date from a Chinese/ISO question without hiding ambiguity."""
    fallback = fallback or datetime.now(tz=UTC).date()
    full = re.search(
        r"(?P<year>20\d{2})\s*(?:年|[-/.])\s*(?P<month>0?[1-9]|1[0-2])\s*"
        r"(?:月|[-/.])\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*(?:日|号)?",
        question,
    )
    if full:
        try:
            resolved = date(
                int(full.group("year")), int(full.group("month")), int(full.group("day"))
            )
            return resolved, "已从问题中识别到具体业务日期"
        except ValueError:
            return fallback, "问题中的日期无效，已按今天查询"
    month = re.search(r"(?P<year>20\d{2})\s*年\s*(?P<month>0?[1-9]|1[0-2])\s*月", question)
    if month:
        resolved = date(int(month.group("year")), int(month.group("month")), 1)
        return resolved, "已识别到月份，按该月 1 日查询；月内有变更时请写具体日期"
    return fallback, "未指定日期，已按今天查询"


def build_ui(config: LocalAgentConfig | None = None):
    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError("Install the UI: pip install -e '.[ui]'") from exc

    agent = TARCSChatAgent(config)
    if (
        agent.memory.store.count() == 0
        and os.getenv("TARCSMEM_SEED_DEMO", "true").lower() == "true"
    ):
        agent.seed_demo()

    def runtime_status() -> str:
        embedding_name = str(getattr(agent.embedding, "model_name", type(agent.embedding).__name__))
        llm_name = str(getattr(agent.llm, "provider_name", type(agent.llm).__name__))
        llm_model = str(getattr(agent.llm, "model", "自定义模型"))
        cloud_generation = getattr(agent.llm, "provider_name", "") == "DeepSeek API（云端）"
        reranker_name = (
            str(getattr(agent.reranker, "model_name", type(agent.reranker).__name__))
            if agent.reranker
            else "未启用"
        )
        counts = agent.memory.store.status_counts()
        active_count = counts.get("verified_active", 0)
        pending_count = counts.get("pending", 0)
        return (
            '<div class="runtime-status">'
            f"<span><i>回答模型</i><b>{llm_name} · {llm_model}</b></span>"
            f"<span><i>可信记忆</i><b>{active_count} 激活 / {agent.memory.store.count()} 总计</b></span>"
            f"<span><i>人工审核队列</i><b>{pending_count} 条待处理</b></span>"
            f"<span><i>检索与重排</i><b>{embedding_name} / {reranker_name}</b></span>"
            f"<span><i>安全模式</i><b>{agent.memory.security.mode} · "
            f"{'证据会发送至云端模型' if cloud_generation else '仅本机处理'}</b></span>"
            "</div>"
        )

    def ask(question: str, history: list[dict]):
        history = history or []
        if not question.strip():
            return history, "", "请输入问题。"
        try:
            business_date, date_note = resolve_business_date(question)
            result = agent.chat(question, business_date, conversation=history)
            citations = (
                "\n".join(f"- `{item}`" for item in result["citations"]) or "- 无（系统已拒答）"
            )
            trace = result["decision_trace"]
            evidence = (
                "\n\n".join(
                    [
                        f"### {item['source_ref']}\n{item['fact']}\n"
                        f"TARCS: `{item['scores']['tarcs']}` · {'；'.join(item['reasons'])}"
                        for item in result["selected_evidence"]
                    ]
                )
                or "没有满足治理条件的证据。"
            )
            panel = (
                f"<div class='result-badge'>{'已回答' if result['outcome'] == 'answered' else '已拒答'}</div>\n\n"
                f"### 决策摘要\n**业务日期**：`{business_date.isoformat()}` · {date_note}  \n"
                f"**检索路线**：`{trace['route']}`  \n"
                f"**检索查询**：`{result.get('retrieval_query', question)}`  \n"
                f"**Trace ID**：`{result.get('observability', {}).get('trace_id', '—')}` · "
                f"`{result.get('observability', {}).get('latency_ms', '—')} ms`  \n"
                f"**引用**：\n{citations}\n\n"
                f"### 被选中的可信证据\n{evidence}"
            )
            metrics = result.get("generation_metrics", {})
            if metrics:
                panel += (
                    "\n\n### 本次模型生成\n"
                    f"服务：`{metrics.get('provider', 'custom')}` · "
                    f"模型：`{metrics.get('model', 'custom-client')}` · "
                    f"输入：`{metrics.get('prompt_tokens', '—')}` tokens · "
                    f"输出：`{metrics.get('completion_tokens', '—')}` tokens · "
                    f"总耗时：`{metrics.get('total_duration_ms', '—')}` ms · "
                    f"会话上下文：`{result.get('context_messages', 0)}` 条"
                )
            # Gradio 6 Chatbot uses OpenAI-style role/content dictionaries.
            updated = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": str(result["answer"])},
            ]
            return updated, "", panel
        except Exception as exc:  # noqa: BLE001  # UI must surface optional setup failures.
            return history, question, f"## 启动或检索失败\n\n`{exc}`"

    def ingest(
        files,
        source_type: str,
        authority: float,
        valid_from: str,
        valid_to: str,
        tenant_id: str,
        allowed_roles: str,
        classification: str,
    ):
        if not files:
            return "请选择至少一个文档。"
        try:
            start = date.fromisoformat(valid_from) if valid_from else None
            end = date.fromisoformat(valid_to) if valid_to else None
            roles = [item.strip() for item in allowed_roles.split(",") if item.strip()]
            results = []
            for file_path in files:
                records = agent.ingest_file(
                    file_path,
                    SourceType(source_type),
                    authority,
                    start,
                    end,
                    tenant_id=tenant_id or "default",
                    allowed_roles=roles,
                    classification=classification,
                )
                status_counts: dict[str, int] = {}
                for record in records:
                    status_counts[record.status.value] = (
                        status_counts.get(record.status.value, 0) + 1
                    )
                results.append(f"- `{file_path}`：{len(records)} chunks，{status_counts}")
            return "## 入库完成\n\n" + "\n".join(results)
        except Exception as exc:  # noqa: BLE001  # UI must surface ingestion failures.
            return f"## 入库失败\n\n`{exc}`"

    def ingest_sec(cik: str, user_agent: str):
        try:
            records = agent.ingest_sec_company(cik, user_agent)
            return f"## SEC EDGAR 入库完成\n\nCIK `{cik}`：新增 {len(records)} 条公开公司事实。"
        except Exception as exc:  # noqa: BLE001  # UI must surface connector failures.
            return f"## SEC EDGAR 入库失败\n\n`{exc}`"

    def ingest_fiqa(limit: int):
        try:
            records = agent.ingest_fiqa_sample(int(limit))
            return (
                "### FiQA 已接入\n\n"
                f"已将 {len(records)} 个文本片段写入本地知识库。它们被标记为 `public_dataset`，"
                "权威度低于企业正式制度；原始文件仅缓存于 `data/external/`。"
            ), runtime_status()
        except Exception as exc:  # noqa: BLE001  # UI must surface dataset failures.
            return f"### FiQA 接入失败\n\n`{exc}`", runtime_status()

    def pending_rows():
        return [
            [
                record.id,
                SOURCE_LABELS[record.source_type],
                record.authority,
                record.source_ref,
                record.fact[:160],
            ]
            for record in agent.pending_memories()
        ]

    def review_memory(
        record_id: str,
        reviewer: str,
        note: str,
        decision: str,
    ):
        if not record_id.strip():
            return "请选择或填写待审核记忆 ID。", pending_rows(), runtime_status()
        try:
            reviewed = agent.memory.review(record_id, decision, reviewer, note)
            label = "批准并激活" if decision == "approve" else "驳回"
            message = (
                f"### 审核完成\n\n`{reviewed.id}` 已**{label}**，"
                f"当前状态：`{reviewed.status.value}`。本次决定已写入审计轨迹。"
            )
            return (
                message,
                pending_rows(),
                runtime_status(),
            )
        except Exception as exc:  # noqa: BLE001  # UI must surface review failures.
            return f"### 审核未执行\n\n`{exc}`", pending_rows(), runtime_status()

    def audit(record_id: str):
        if not record_id:
            return "请输入记忆 ID。"
        events = agent.memory.audit_trail(record_id)
        if not events:
            return "未找到审计记录。"
        lines = [
            f"- `{item['at']}` **{item['event_type']}**：`{item['detail']}`" for item in events
        ]
        return "## 审计轨迹\n\n" + "\n".join(lines)

    def observability_snapshot():
        return {
            "metrics": agent.memory.observability.metrics.snapshot(),
            "recent_spans": agent.memory.observability.tracer.buffer.recent(50),
            "privacy": "观测数据不保存原始问题、文档正文或密钥",
        }

    css = """
    :root { --ink:#192132; --muted:#667085; --line:#e6eaf2; --brand:#5b48ed; --aqua:#27c8c4; --paper:#fff; --soft:#f5f7fc; }
    .gradio-container { max-width:1440px !important; padding:28px 36px 44px !important; background:radial-gradient(circle at 0 0,#eae8ff 0,transparent 28%),#f6f7fb !important; }
    #hero { position:relative; overflow:hidden; min-height:206px; padding:34px 42px; border-radius:28px; color:#fff; box-shadow:0 20px 42px rgba(65,50,179,.22); background:linear-gradient(120deg,#17134b 0%,#5140dc 54%,#1ebdc1 140%); }
    #hero:after { content:""; position:absolute; inset:-60px -40px auto auto; width:290px; height:290px; border:1px solid rgba(255,255,255,.3); border-radius:50%; box-shadow:0 0 0 28px rgba(255,255,255,.07),0 0 0 56px rgba(255,255,255,.04); }
    .hero-kicker { display:inline-flex; gap:8px; align-items:center; margin-bottom:14px; font-size:12px; letter-spacing:.08em; color:#e5fffe; }
    .hero-kicker:before { content:""; width:8px; height:8px; border-radius:50%; background:#49f3cf; box-shadow:0 0 0 5px rgba(73,243,207,.18); }
    #hero h1 { position:relative; z-index:1; margin:0 0 10px; color:#fff !important; font-size:38px; line-height:1.2; letter-spacing:-.04em; }
    #hero p { position:relative; z-index:1; max-width:690px; margin:0; color:#f1f2ff !important; font-size:16px; line-height:1.75; }
    .runtime-status { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:18px 0 22px; }
    .runtime-status span { min-height:74px; display:flex; flex-direction:column; justify-content:center; gap:5px; background:rgba(255,255,255,.88); border:1px solid #fff; border-radius:16px; padding:13px 16px; box-shadow:0 8px 20px rgba(41,53,81,.06); }
    .runtime-status i { color:#818ba0; font-size:12px; font-style:normal; } .runtime-status b { color:var(--ink); font-size:14px; }
    .tabs { background:transparent !important; } .tab-nav { gap:8px !important; border:0 !important; }
    .tab-nav button { border-radius:12px !important; color:#697386 !important; font-weight:650 !important; } .tab-nav button.selected { color:var(--brand) !important; background:#eceaff !important; }
    #chat-panel, #evidence-panel, #ingest-card, #governance-card { background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:22px; padding:22px; box-shadow:0 10px 28px rgba(35,45,73,.05); }
    #evidence-panel { background:linear-gradient(155deg,#fff 0%,#f6fbff 100%); }
    .panel-title { color:var(--ink); margin:0 0 4px; font-size:18px; font-weight:800; letter-spacing:-.02em; }
    .panel-subtitle { margin:0 0 16px; color:var(--muted); font-size:13px; line-height:1.6; }
    .date-hint { margin:10px 0 14px; padding:10px 12px; border-radius:11px; color:#6259a6; background:#f1efff; font-size:13px; }
    .result-badge { display:inline-block; background:#e8fff5; color:#087443; border:1px solid #bff1d8; border-radius:99px; padding:5px 11px; font-size:12px; font-weight:800; }
    #send-btn { min-height:48px; border:0 !important; border-radius:13px !important; font-size:15px !important; font-weight:750 !important; background:linear-gradient(105deg,#5a48ed,#2d7df4) !important; box-shadow:0 10px 18px rgba(74,79,229,.24); }
    #question textarea { font-size:15px !important; } .gr-button { border-radius:12px !important; }
    .message { border-radius:16px !important; } footer { opacity:.45; }
    @media (max-width:960px) { .runtime-status { grid-template-columns:repeat(3,1fr); } }
    @media (max-width:760px) { .gradio-container { padding:16px !important; } #hero { min-height:0; padding:28px 24px; } #hero h1 { font-size:30px; } .runtime-status { grid-template-columns:repeat(2,1fr); } }
    """
    with gr.Blocks(title="TARCS-Mem · 企业可信知识 Agent") as demo:
        gr.HTML(
            "<section id='hero'><div class='hero-kicker'>本地运行 · 可追溯 · 有边界</div>"
            "<h1>可信企业知识工作台</h1>"
            "<p>把制度、业务资料和长期记忆变成可核验的回答。每一次回答，都能看到引用、时效与裁决理由。</p></section>"
        )
        status = gr.HTML(runtime_status())
        with gr.Tabs():
            with gr.Tab("💬 对话与证据"):
                with gr.Row():
                    with gr.Column(scale=3, elem_id="chat-panel"):
                        gr.HTML(
                            "<div class='panel-title'>问一个业务问题</div><p class='panel-subtitle'>系统自动识别问题里的业务日期；没有日期时，默认按今天查询。</p>"
                        )
                        chatbot = gr.Chatbot(label="对话", height=460)
                        question = gr.Textbox(
                            label="你的问题",
                            placeholder="例如：2026 年 8 月华南区销售折扣上限是多少？",
                            lines=2,
                            elem_id="question",
                        )
                        with gr.Row():
                            submit = gr.Button("查证并回答", variant="primary", elem_id="send-btn")
                        gr.HTML(
                            "<div class='date-hint'>✦ 不用手动填日期：支持“2026年9月12日”或“2026-09-12”；不写则按今天。</div>"
                        )
                        with gr.Row():
                            demo_policy = gr.Button("试试：制度版本")
                            demo_abstain = gr.Button("试试：证据不足")
                    with gr.Column(scale=2, elem_id="evidence-panel"):
                        gr.HTML(
                            "<div class='panel-title'>证据与裁决</div><p class='panel-subtitle'>回答不是黑盒：这里会展示依据、时效与 TARCS 排序理由。</p>"
                        )
                        evidence_panel = gr.Markdown(
                            "**等待你的问题。**\n\n系统将从已治理记忆中选择有效证据，信息不足时会明确拒答。"
                        )
                submit.click(ask, [question, chatbot], [chatbot, question, evidence_panel])
                question.submit(ask, [question, chatbot], [chatbot, question, evidence_panel])
                demo_policy.click(lambda: "2026年8月华南区销售折扣上限是多少？", outputs=question)
                demo_abstain.click(
                    lambda: "2026年10月北区培训津贴是否已提高到900元？", outputs=question
                )
            with gr.Tab("📥 知识与数据集"):
                with gr.Row():
                    with gr.Column(scale=3, elem_id="ingest-card"):
                        gr.HTML("<div class='panel-title'>上传你拥有授权的资料</div>")
                        gr.Markdown(
                            "文件仅在本机解析和存储；不要上传公司机密、客户数据、密钥或未经授权的文档。"
                        )
                        files = gr.File(
                            label="PDF / DOCX / Markdown / CSV",
                            file_count="multiple",
                            type="filepath",
                        )
                    with gr.Column(scale=2):
                        gr.Markdown("### 写入治理参数\n它们决定一条信息能否成为可回答证据。")
                        source_type = gr.Dropdown(
                            choices=[(SOURCE_LABELS[item], item.value) for item in SourceType],
                            value=SourceType.OFFICIAL_POLICY.value,
                            label="来源类别",
                        )
                        authority = gr.Slider(0, 1, value=1, step=0.05, label="权威等级")
                with gr.Row():
                    valid_from = gr.Textbox(label="业务生效日（可选，YYYY-MM-DD）")
                    valid_to = gr.Textbox(label="业务失效日（可选，YYYY-MM-DD）")
                with gr.Row():
                    tenant_id = gr.Textbox(label="租户 ID", value="default")
                    allowed_roles = gr.Textbox(
                        label="允许角色（逗号分隔）",
                        placeholder="例如：finance,policy-owner；留空表示租户内可见",
                    )
                    classification = gr.Dropdown(
                        choices=["public", "internal", "confidential", "restricted"],
                        value="internal",
                        label="数据分级",
                    )
                ingest_button = gr.Button("安全扫描并写入本地库", variant="primary")
                ingest_result = gr.Markdown()
                ingest_button.click(
                    ingest,
                    [
                        files,
                        source_type,
                        authority,
                        valid_from,
                        valid_to,
                        tenant_id,
                        allowed_roles,
                        classification,
                    ],
                    ingest_result,
                )
                gr.Markdown(
                    "---\n### 公开基准数据 · FiQA（金融检索）\n用于证明 RAG 检索/重排能力，不代表企业政策知识。按你选择的数量从公开 API 拉取，并在本地缓存该样本。"
                )
                with gr.Row():
                    fiqa_limit = gr.Slider(
                        25, 500, value=100, step=25, label="导入文档数（建议先用 100）"
                    )
                    fiqa_button = gr.Button("下载并接入 FiQA", variant="primary")
                fiqa_result = gr.Markdown()
                fiqa_button.click(ingest_fiqa, fiqa_limit, [fiqa_result, status])
                gr.Markdown(
                    "---\n### 公开业务资料 · SEC EDGAR\n仅用于公开资料 PoC；填写合规应用名和联系邮箱。"
                )
                with gr.Row():
                    cik = gr.Textbox(label="公司 CIK")
                    sec_user_agent = gr.Textbox(
                        label="SEC User-Agent", placeholder="TARCS-Mem your-email@example.com"
                    )
                sec_button = gr.Button("拉取公开公司事实")
                sec_result = gr.Markdown()
                sec_button.click(ingest_sec, [cik, sec_user_agent], sec_result)
            with gr.Tab("🛡️ 记忆治理与审计"):
                gr.Markdown(
                    "这里呈现没有自动激活的记忆，并要求具名人工审核。"
                    "审核不会允许低权威来源静默覆盖现行制度。"
                )
                refresh = gr.Button("刷新待审核记忆")
                pending = gr.Dataframe(
                    headers=["记忆 ID", "来源", "权威", "来源引用", "事实摘要"],
                    value=pending_rows(),
                    interactive=False,
                    label="待审核 / 冲突记忆",
                )
                refresh.click(pending_rows, outputs=pending)
                gr.Markdown("### 人工审核")
                with gr.Row():
                    review_record_id = gr.Textbox(
                        label="待审核记忆 ID",
                        placeholder="从上方表格复制记忆 ID",
                    )
                    reviewer = gr.Textbox(
                        label="审核人",
                        placeholder="姓名或企业账号（必填）",
                    )
                review_note = gr.Textbox(
                    label="审核备注",
                    placeholder="写明依据、工单号或拒绝原因，便于事后追溯",
                    lines=2,
                )
                with gr.Row():
                    approve_button = gr.Button("批准并激活", variant="primary")
                    reject_button = gr.Button("驳回", variant="stop")
                review_result = gr.Markdown()
                approve_button.click(
                    lambda record_id, reviewer_name, note: review_memory(
                        record_id, reviewer_name, note, "approve"
                    ),
                    [review_record_id, reviewer, review_note],
                    [review_result, pending, status],
                )
                reject_button.click(
                    lambda record_id, reviewer_name, note: review_memory(
                        record_id, reviewer_name, note, "reject"
                    ),
                    [review_record_id, reviewer, review_note],
                    [review_result, pending, status],
                )
                gr.Markdown("### 审计轨迹")
                record_id = gr.Textbox(label="记忆 ID")
                audit_button = gr.Button("查看审计轨迹")
                audit_result = gr.Markdown()
                audit_button.click(audit, record_id, audit_result)
            with gr.Tab("📊 运行观测"):
                gr.Markdown(
                    "查看 GuardWrite、GuardRead、查询延迟和安全事件。"
                    "Trace 只记录长度、数量、路由和状态，不记录原始问题或文档正文。"
                )
                refresh_observability = gr.Button("刷新运行指标")
                observability_panel = gr.JSON(
                    value=observability_snapshot(),
                    label="安全观测快照",
                )
                refresh_observability.click(observability_snapshot, outputs=observability_panel)
    # Gradio 6 applies custom CSS at launch time rather than in Blocks().
    demo._tarcsmem_css = css
    return demo


def launch_ui(
    config: LocalAgentConfig | None = None, host: str = "127.0.0.1", port: int = 7860
) -> None:
    demo = build_ui(config)
    demo.launch(
        server_name=host,
        server_port=port,
        inbrowser=True,
        css=getattr(demo, "_tarcsmem_css", ""),
    )
