# TARCS-Mem

> A production-oriented reference implementation of **trusted enterprise memory governance** for RAG and AI agents.

[中文说明](README.zh-CN.md) · [MCP & OpenAI integrations](docs/INTEGRATIONS.md) · [DeepSeek cloud setup (中文)](docs/DEEPSEEK_API_CN.md) · [Production deployment](docs/PRODUCTION_DEPLOYMENT.md) · [Architecture](docs/ARCHITECTURE.md) · [Algorithm](docs/ALGORITHM.md) · [First GitHub upload (中文)](docs/GITHUB_FIRST_UPLOAD_CN.md)

TARCS-Mem answers a question that ordinary memory/RAG layers leave open: **which new facts may become active enterprise memory, and which evidence may be used to answer right now?**

It is deliberately not another general-purpose chatbot. It is a reusable governance layer for policy Q&A, ERP/operations assistants, and other enterprise agents where stale, low-authority, or unverified information is harmful.

![TARCS-Mem governed answer with source and decision trace](docs/demo/assets/02-answer-v07.jpg)

| Ordinary RAG | TARCS-Mem |
| --- | --- |
| stores extracted text directly | admits, holds for review or rejects each memory |
| retrieves the closest chunks | filters tenant, role, status and business time before ranking |
| overwrites or ignores conflicting versions | preserves history and requires explainable supersession |
| asks the model to cite | blocks missing/invented citations and unauthorized cloud egress |

## What is implemented

- **GuardWrite** – admission policy for automatic memory writes; source provenance, evidence completeness, confidence and durable value decide `verified_active`, `pending`, or `rejected`.
- **Version and conflict governance** – append-only audit events; new authoritative records supersede older active records instead of overwriting them. Equal-authority conflicts remain pending for human review.
- **Bi-temporal memory** – separates business `valid_time` from system `observed_at`.
- **GuardRead / TARCS** – hybrid lexical + semantic-style retrieval, RRF fusion, hard validity/status constraints, then Time–Authority–Reliability–Cost scoring and token-budgeted MMR context selection.
- **Evidence-aware abstention** – returns a structured abstention when evidence is unavailable or unresolved conflicts remain.
- **Human review loop** – named reviewers can approve or reject pending memories with notes; low-authority evidence cannot silently override an active policy.
- **Enterprise security baseline** – credential blocking, PII redaction, tenant boundaries, document role ACLs, classification labels and optional bearer authentication.
- **Privacy-safe observability** – Prometheus metrics, bounded in-memory spans, trace IDs and P95 latency without raw query/document capture.
- **Reproducible evaluation** – synthetic governance cases plus a real labelled FiQA test/qrels candidate-pool benchmark.
- **Local or cloud generation** – switch between local Ollama/Qwen3 and the DeepSeek cloud API without changing the governance path.
- **Cloud egress enforcement** – DeepSeek (or another cloud adapter) receives evidence only after a classification allow-list check; `confidential` and `restricted` are blocked by default, with privacy-safe audit events and metrics.
- **Citation verification** – a generated answer must cite an exact source label from the governed evidence pack; missing or invented citations are blocked before return.
- **MCP v2 integration** – any MCP host can search governed memory; agent-authored proposals are forced into low-authority human review and cannot self-promote to policy.
- **OpenAI-compatible gateway** – existing chat clients can use `/v1/chat/completions` while TARCS citation, time, access and egress controls remain enforced.
- **LangChain and LlamaIndex adapters** – convert governed evidence into each framework's native retriever with one function call; neither adapter can read the unfiltered candidate pool.
- **Incremental Confluence connector** – Confluence Cloud REST API v2 cursor pagination, version/hash checkpoints, deterministic retry-safe IDs, safe deletion handling and human-review defaults.
- **Production-oriented delivery** – retry-safe write idempotency, rate limits, liveness/readiness endpoints, request IDs, non-root Docker runtime, audit log, 90 tests, Python 3.11/3.12 CI, clean-wheel/extras/Docker checks, dependency automation and explicit security/deployment guidance.

`TARCS-Mem` is a reference implementation, not a claim of production certification. Request-body roles are demo inputs, not trusted identity claims. A real production deployment must bind tenant/roles from OIDC/SSO, externalize authorization policy, add encryption/key management, malware scanning, retention controls, SIEM export, backup/restore and load/red-team tests.

## Architecture

```text
Documents / conversations / approval records
                  |
            GuardWrite
 extract -> schema validate -> admission -> conflict resolver
                  |
  append-only audit events + active memory projection
                  |
User question -> hybrid retrieval -> RRF -> TARCS constraints/ranking
                  |                         |
                  |                    token-budget MMR
                  v                         v
              evidence pack -> verification -> answer / clarify / abstain
```

Read the formal choices in [docs/ALGORITHM.md](docs/ALGORITHM.md) and the component boundaries in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/<your-account>/tarcsmem.git
cd tarcsmem
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api]'

# load deterministic synthetic records and run the benchmark
tarcsmem seed --db ./data/tarcsmem.db
tarcsmem evaluate --db ./data/tarcsmem.db

# inspect a grounded response at a business date
tarcsmem ask --db ./data/tarcsmem.db \
  --question '2026年8月华南区销售折扣上限是多少？' \
  --as-of 2026-08-15
```

Start an API server:

```bash
tarcsmem serve --db ./data/tarcsmem.db --host 0.0.0.0 --port 8000
curl -X POST http://localhost:8000/v1/query \
  -H 'content-type: application/json' \
  -d '{"question":"2026年8月华南区销售折扣上限是多少？","as_of":"2026-08-15","tenant_id":"default","roles":[]}'
```

Or run the API in a container:

```bash
docker compose up --build
```

For generated, cited answers through the service API, install the agent/provider extras and call `POST /v1/chat`; it follows the same TARCS retrieval and policy gates as the UI:

```bash
pip install -e '.[api,agent,cloud]'
curl -X POST http://localhost:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"question":"2026年8月华南区销售折扣上限是多少？","as_of":"2026-08-15","tenant_id":"default","roles":[]}'
```

The API accepts tenant and role fields only as local-demo inputs. Put it behind OIDC/SSO and inject verified claims before production. The full pilot-to-production checklist is in [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md).

### Connect existing agent and chat tools

Run TARCS-Mem as an MCP v2 stdio server:

```bash
pip install -e '.[mcp]'
tarcsmem-mcp
```

Or point an OpenAI-compatible client at `http://127.0.0.1:8000/v1` and use model
`tarcsmem-governed`. The compatibility endpoint is deliberately non-streaming
so citation verification can fail closed before response bytes are released.
See [the integration guide](docs/INTEGRATIONS.md) for host configuration, curl
examples and security boundaries.

Use TARCS-Mem as a native retriever in an existing framework:

```python
from datetime import date
from tarcsmem import TARCSMemoryService, as_langchain_retriever, as_llamaindex_retriever

memory = TARCSMemoryService("./data/tarcsmem.db")
langchain_retriever = as_langchain_retriever(memory, date.today())
llamaindex_retriever = as_llamaindex_retriever(memory, date.today())
```

Install with `pip install -e '.[integrations]'`. Both adapters return only evidence
that passed tenant/role, status, business-time and conflict gates.

Incrementally sync a real Confluence Cloud space into the same governance path:

```bash
export TARCSMEM_CONFLUENCE_BASE_URL=https://your-site.atlassian.net
export TARCSMEM_CONFLUENCE_EMAIL=you@example.com
export TARCSMEM_CONFLUENCE_SPACE_ID=123456
export TARCSMEM_CONFLUENCE_API_TOKEN='read-from-your-secret-manager'
tarcsmem sync-confluence --db ./data/tarcsmem.db
```

The default source type is `meeting_note`, so imported pages wait for review. Only
use `--source-type official_policy --authority 1.0` for a space whose publication
workflow is itself an approved policy control. See [the connector guide](docs/INTEGRATIONS.md#confluence-cloud-incremental-sync).

### Five-minute local UI preview

The default first-run profile uses dependency-light Hash retrieval and a deterministic evidence renderer. It needs no API key, Ollama process or model download:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[ui,dev]'
tarcsmem ui --db ./data/tarcsmem-demo.db
```

Open `http://127.0.0.1:7860`. This preview still runs GuardWrite, conflict governance,
TARCS filtering/ranking, abstention, citation verification and audit logging. The renderer is not
an LLM and does no reasoning; it exposes selected evidence with exact citations so the complete
governance path is reproducible. Follow [docs/LOCAL_AGENT.md](docs/LOCAL_AGENT.md) to explicitly
enable Qwen3, BGE embeddings/reranking and the complete local RAG path.

### DeepSeek cloud generation (no local LLM)

Revoke any key that has appeared in chat, screenshots or logs. Put a newly generated key only in
an untracked `.env` file, then load it into the current shell:

```bash
pip install -e '.[ui,dev,api,cloud]'
cp .env.example .env
# Edit .env: TARCSMEM_LLM_PROVIDER=deepseek and DEEPSEEK_API_KEY=<new key>
set -a
source .env
set +a
export TARCSMEM_EMBEDDING_BACKEND=hash
export TARCSMEM_RERANKER=off
tarcsmem ui --db ./data/tarcsmem-deepseek.db
```

The default cloud model is `deepseek-v4-flash` in non-thinking mode. Selected evidence and the
question leave the machine in cloud mode, so use only data authorized for that provider. The
enforced default permits only `public,internal` classifications; confidential/restricted evidence
blocks cloud generation until a security owner changes `TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS`.
See
[the DeepSeek setup and security guide](docs/DEEPSEEK_API_CN.md).

## Full local conversational Agent

The project also contains a complete local Agent path: Ollama/Qwen3 for dialogue, BGE-M3 embeddings, BGE reranking, Qdrant vector search, document upload, cited answers, a public SEC EDGAR connector, and a Gradio interface. Follow [docs/LOCAL_AGENT.md](docs/LOCAL_AGENT.md). It runs without a paid model API, but needs local model downloads and suitable hardware.

## Example result

```json
{
  "outcome": "answered",
  "answer": "Based on 1 governed evidence record(s): 华南区销售折扣上限为5%，自2026-07-01起生效。",
  "citations": ["POLICY-SALES-2026-07#1"],
  "decision_trace": {
    "as_of": "2026-08-15",
    "selected": [{"id": "sales-v2", "tarcs_score": 0.91}],
    "excluded": [{"id": "sales-meeting-note", "reason": "pending memory is not eligible"}]
  }
}
```

The answer renderer is intentionally deterministic. In a real LLM application, send only `selected_evidence` to the model and require structured citations; retain the same verification and abstention gates.

## Core record schema

Each memory carries provenance and governance metadata:

```json
{
  "id": "sales-v2",
  "fact": "华南区销售折扣上限为5%，自2026-07-01起生效。",
  "source_type": "official_policy",
  "authority": 1.0,
  "source_ref": "POLICY-SALES-2026-07#1",
  "valid_from": "2026-07-01",
  "valid_to": null,
  "observed_at": "2026-06-20T09:00:00+00:00",
  "conflict_key": "sales_discount_limit:华南区",
  "status": "verified_active"
}
```

## Evaluation

The benchmark compares naive lexical retrieval with TARCS-Mem on controlled difficult cases. It reports:

- answer correctness;
- freshness / authoritative-source selection;
- correct abstention;
- average selected evidence and estimated context tokens.

The checked-in real-data report now uses **120 FiQA test queries and 610 candidate documents**. It compares lexical, hashed semantic, RRF, and complete TARCS ablations with 1,000-sample bootstrap confidence intervals. TARCS reaches Recall@10 **0.4446**, MRR@10 **0.4839**, and NDCG@10 **0.3783**, versus **0.3624**, **0.3748**, and **0.2988** for the lexical baseline. The report also exposes the latency trade-off. It remains a qrel-plus-distractor bounded pool, not a full-corpus BEIR leaderboard result. See [docs/EVALUATION.md](docs/EVALUATION.md) and the machine-readable [report](docs/benchmarks/fiqa-public-report.json).

Core regression tests additionally cover zero-overlap RRF pollution, relevance filtering before token budgeting, true greedy document-only MMR, and candidate oversampling before ACL/status/time filtering. These tests do not retroactively claim a higher FiQA score.

A verified 85-second v0.7 Chinese demo video and timed narration script are available under [docs/demo](docs/demo/).

For a portfolio-quality evaluation, combine the repository's synthetic governance scenarios with LongMemEval (memory), FinQA (financial document/table reasoning), and optionally BIRD Mini-Dev (Text-to-SQL). The exact source links, intended use and non-redistribution rule are in [docs/DATASET.md](docs/DATASET.md).

## Repository layout

```text
src/tarcsmem/       core package
tests/              unit and workflow tests
docs/               architecture, algorithm, data and security notes
examples/           copy-paste MCP and OpenAI-compatible integrations
.github/workflows/  CI
Dockerfile          local API image
```

## Roadmap

- [ ] Pluggable vector DB adapters (pgvector/Qdrant)
- [x] MCP v2 stdio server with governed search and fail-safe proposals
- [x] OpenAI-compatible non-streaming chat-completions facade
- [x] Native LangChain and LlamaIndex governed retrievers
- [x] Confluence Cloud REST API v2 incremental connector
- [x] Built-in privacy-safe traces and Prometheus metrics
- [x] Tenant-aware retrieval and document-level role ACL filtering
- [ ] OIDC/SSO-derived claims, external Casbin/OPA policy and OTLP export
- [x] Human-review queue/UI for pending memories with an auditable approve/reject decision
- [ ] Learned TARCS ranker trained on adjudicated labels
- [ ] Optional GraphRAG adapter only for demonstrated multi-hop entity queries

## License

MIT. Do not include customer documents, API keys, internal business rules, or personally identifiable data in a public repository.
