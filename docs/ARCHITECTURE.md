# Architecture

## Scope

TARCS-Mem is a governance layer between memory ingestion/retrieval and an LLM Agent. It is intentionally independent of LangChain, LlamaIndex, a vector database, and a model provider. This permits it to be adopted as an adapter rather than a replacement for an existing RAG stack.

This document describes the current v0.8 component boundaries. The
[governance pipeline design](GOVERNANCE_PIPELINE_DESIGN.md) is the post-v0.8 target for versioned
policy bundles, a tamper-evident audit envelope, rebuildable active-memory projections,
answer-centric evidence chains and configurable retrieval plugins. Proposed interfaces in that
document are not claims about current behavior.

For the broader product-facing evolution, see the [next-stage upgrade plan](NEXT_STAGE_UPGRADE_PLAN.md),
which covers architecture paradigms, console UX, PoC-to-production readiness, community backlog
and service boundaries.

## Write path: GuardWrite

1. An upstream extractor creates a typed `MemoryRecord` with tenant, roles and classification.
2. The security gate blocks credential-like content and redacts common PII before a durable memory write.
3. `MemoryAdmission` checks source class, evidence, extraction confidence and durable value.
4. `ConflictResolver` compares overlapping active records in the same tenant and `conflict_key`.
5. Every decision appends an audit event. A newer authoritative record supersedes an old record; it never silently overwrites the source history.
6. Pending records enter a named human-review queue. Approval requires traceable evidence, and an overlapping record cannot replace an active source unless it has a business effective date and strictly higher authority.

## Read path: GuardRead

1. The query router labels the route. The reference router is rule-based; production can replace it with a calibrated classifier.
2. Tenant and role ACL constraints reject inaccessible records before scoring; Qdrant receives the tenant filter server-side.
3. Hybrid lexical and semantic-like rankings are fused with RRF.
4. Hard constraints reject non-active and out-of-valid-time records before LLM context assembly.
5. TARCS ranks remaining records. A greedy MMR selector fits a diverse evidence set under a token budget.
6. If no grounded evidence survives, the service abstains. An upstream LLM must only receive selected evidence and return source citations.
7. When the configured LLM is cloud-hosted, an egress gate checks the selected records' classifications immediately before generation. The default policy permits only `public` and `internal`; it audits and blocks the call otherwise.

## Observability boundary

GuardWrite, GuardRead and review operations emit privacy-safe counters and nested spans. Raw questions and documents stay outside telemetry; query audit events contain a hash, length, route and outcome. The reference API exports Prometheus text and a bounded local span snapshot.

## Integration boundary

The native API, OpenAI-compatible facade and MCP v2 server all call the same
GuardWrite/GuardRead services. They do not implement parallel retrieval paths.
OpenAI client system messages are discarded before the server-owned governance
prompt is built. MCP proposals are hard-coded as low-authority `user_claim`
records, so a model cannot choose `official_policy` in a tool call and activate
its own output.

## Interfaces to replace in production

| Reference component | Production replacement |
| --- | --- |
| SQLite store | PostgreSQL/pgvector, Qdrant plus an immutable audit store |
| Token overlap semantic score | BGE-M3/e5 embeddings and cross-encoder reranker |
| Rule-based router | calibrated classifier or tool router |
| Deterministic answer renderer | cited LLM response with atomic claim verifier |
| Local process memory | stateless API service, queue for ingestion, cache and rate limits |
| Environment classification allow-list | centrally managed DLP/egress policy with provider, region and retention constraints |

## Why GraphRAG and multi-agent review are not V1 dependencies

GraphRAG is justified only after the benchmark proves relation-heavy multi-hop questions are a material failure mode. Multi-agent debate is justified only after a single verifier plus deterministic policy rules are insufficient. Both add latency and evaluation complexity and should be adapters, not the core of the project.
