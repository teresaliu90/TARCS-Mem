# Changelog

## Unreleased

- Published a customer-data-free Confluence connector contract fixture kit covering cursor
  pagination, duplicate delivery, bounded retry, partial failure, ACL/classification mapping and
  explicit missing-page confirmation.
- Made Confluence record identity sensitive to both version and content hash, so changed content
  cannot be skipped if an upstream version number is unexpectedly reused.
- Retained unconfirmed missing pages in checkpoints and recorded explicit expiry events without
  deleting memory or audit history.

## 0.8.0 - 2026-08-06

- Added a beginner-friendly React governance console served directly by FastAPI at `/console/`.
- Added a governance health overview, governed query sandbox, searchable memory inventory, human review workspace, privacy-safe trace view and integration center.
- Added console APIs for filtered memory inventory, version/audit detail, health summaries and secret-free integration status.
- Added session-only Bearer token configuration so protected pilots can use the console without persisting credentials.
- Packaged the compiled console inside the Python wheel and added deterministic TypeScript/build checks to CI.
- Expanded the API suite to 92 tests, including protection of governance data while static console assets remain publicly loadable.

## 0.7.0 - 2026-08-06

- Added an official MCP Python SDK v2 server with governed search, a governance resource and a fail-safe proposal tool that cannot auto-activate agent-authored claims.
- Added an OpenAI-compatible non-streaming chat-completions facade with standard choices/usage fields and additive TARCS citation, decision-trace and observability metadata.
- Prevented client-provided system messages from replacing server-owned evidence, citation and cloud-egress policy.
- Added real in-memory MCP protocol tests and compatibility API regression tests.
- Added a focused integration guide for MCP hosts, OpenAI-compatible clients and native governance endpoints.

## 0.6.0 - 2026-08-06

- Added an enforced cloud-egress classification gate before cloud generation, plus privacy-safe audit and Prometheus metrics.
- Added structural generated-citation verification that blocks missing and invented source labels before an answer is returned.
- Added retry-safe idempotency for memory writes/reviews, direct-peer API rate limits, authenticated readiness, response request IDs and a non-root container runtime.
- Moved the grounding relevance floor before token-budgeted selection, excluded zero-overlap records from RRF, and corrected MMR to greedily select diverse document content.
- Added vector-candidate oversampling before ACL/status/time filtering to prevent false abstention behind inaccessible candidates.
- Added Python 3.11/3.12 CI, formatting enforcement and a clean-wheel install/CLI smoke test.
- Added a zero-credential extractive demo provider and dependency-light defaults so the complete UI governance flow runs before users configure an LLM or model download.
- Added governed `POST /v1/chat` and immediate vector indexing for API ingests after the Agent is enabled.
- Added a production deployment guide, contribution/code-of-conduct materials, issue/PR templates and Dependabot configuration.

## 0.5.0

- Added a dependency-free DeepSeek cloud generation adapter with explicit provider switching.
- Added retry, timeout, token/cache metrics, secure key handling and five mocked cloud tests.
- Updated the UI to disclose whether evidence is processed locally or sent to a cloud model.
- Expanded the real FiQA evaluation from 20 to 120 labelled test queries and 610 candidate documents.
- Added lexical, hashed-semantic, RRF and complete-TARCS ablation groups.
- Added deterministic 1,000-sample bootstrap confidence intervals and retrieval latency reporting.
- Added a tag-driven GitHub Release workflow, release notes, checksums and packaged benchmark artifacts.
- Added an approximately two-minute Chinese product demo video, screenshots and narration script.

## 0.4.0

- Added credential blocking, PII redaction and security scanning before ingestion/review writes.
- Added tenant-scoped conflicts, pre-ranking tenant boundaries, document role ACLs and classifications.
- Added optional API bearer authentication and privacy-minimal health checks.
- Added Prometheus metrics, bounded spans, trace IDs and privacy-safe audit logging.
- Added a reproducible real FiQA test/qrels candidate-pool evaluation and checked-in report.
- Expanded the automated suite to 52 governance, security, API, observability and evaluation tests.

## 0.3.0

- Added an auditable human review workflow for pending memories.
- Prevented human approval from silently weakening an active source.
- Exposed governance status counts through the health endpoint and UI.
- Added a bilingual project overview and first-upload GitHub guide.
- Hardened repository ignores for local databases, vector indexes, archives and private working files.

## 0.2.1

- Added the complete local Agent path with Qwen3/Ollama, BGE, Qdrant and Gradio.

## 0.1.0

- Added the GuardWrite, conflict governance, TARCS retrieval and evaluation reference core.
