# Production deployment guide

This repository ships a runnable reference stack, not a certified enterprise platform. Use this guide to turn the reference into a bounded pilot before any customer or employee data is connected.

## 1. Start with a controlled pilot

Choose one policy-Q&A or operational workflow with a named data owner, a finite document set and a frozen evaluation set. Define before launch:

- approved tenants, roles and document classifications;
- a data-retention rule and deletion owner;
- whether inference is local or an approved cloud provider;
- success criteria: grounded-answer rate, correct abstention, Recall@k, P95 latency, ACL denials and zero unapproved egress events.

Do not use request-body `tenant_id` or `roles` as identity in a public deployment. They exist only to make the reference API testable.

## 2. Configure the service

Copy `.env.example` to an untracked `.env`, set a long random `TARCSMEM_API_KEY`, and keep it in a secret manager for real deployments. The default `extractive` provider is a zero-credential functional demo, not a production reasoning model. For a local LLM path use `TARCSMEM_LLM_PROVIDER=ollama`.

The reference API also includes two pilot safeguards:

```dotenv
TARCSMEM_RATE_LIMIT_REQUESTS_PER_MINUTE=120
TARCSMEM_IDEMPOTENCY_TTL_HOURS=24
```

The in-process rate limiter is keyed to the direct network peer, intentionally does not trust forwarding headers, and is not a substitute for a distributed gateway limit. For retry-safe writes, send an 8–128 character `Idempotency-Key` on `POST /v1/memories` and review requests. The server hashes the request for comparison, persists the first successful response for the configured TTL, replays an identical retry, and rejects reuse of a key with a different body.

For DeepSeek cloud generation, set `TARCSMEM_LLM_PROVIDER=deepseek` and provide `DEEPSEEK_API_KEY` through your secret manager. The gate below still runs before every generation call:

```dotenv
# Default: no confidential/restricted evidence may leave the environment.
TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS=public,internal
```

Changing that allow-list is a security-policy change. It is not suitable as a per-request switch. The application records only provider/outcome/classification in its egress audit event, never prompt or document content.

## 3. Run the reference container stack

```bash
cp .env.example .env
# Edit .env locally; never commit it.
docker compose up --build
```

The API is on `http://127.0.0.1:8000`; Qdrant is loopback-bound by default. The compose file is convenient for development or a single-host pilot. Pin image digests, use a private registry, and run vulnerability scanning before a managed environment.

The service exposes:

| Endpoint | Purpose |
| --- | --- |
| `GET /healthz` | public, content-free liveness check |
| `GET /readyz` | authenticated, content-free SQLite readiness probe |
| `POST /v1/memories` | governed memory ingestion |
| `POST /v1/query` | deterministic governed retrieval response |
| `POST /v1/chat` | governed retrieval plus configured LLM generation |
| `GET /v1/answers/{answer_id}/audit` | privacy-safe answer evidence chain with tenant/ACL rechecks |
| `GET /v1/models` | OpenAI-compatible governed model discovery |
| `POST /v1/chat/completions` | non-streaming OpenAI-compatible governed chat |
| `GET /metrics` | Prometheus-formatted privacy-safe metrics |
| `GET /v1/observability` | bounded local trace/metric snapshot |

`/v1/chat` and `/v1/chat/completions` are unavailable with HTTP 503 until vector/LLM dependencies and configuration are present. They do not bypass TARCS, ACL, valid-time, conflict or egress controls. By default, generated output also needs an exact `[SOURCE: ...]` label from the selected evidence pack; missing or invented labels are blocked. This is structural citation verification, not atomic claim entailment. Every response returns an `X-Request-ID`; retain that identifier in gateway logs rather than collecting raw prompts.

`GET /v1/answers/{answer_id}/audit` returns stable answer/evidence-pack/correlation IDs, selected
memory lineage, aggregate exclusions, policy references and verification results. It excludes raw
questions and evidence content, returns the same `404` for unknown and unauthorized IDs, and
rechecks selected records against the caller's tenant/roles at the original business date. The
reference `tenant_id` and `roles` query parameters are demo inputs, not verified identity. A
production gateway must derive these claims from OIDC/SSO and prevent client overrides.

The response reports `integrity.chain_verified: false` while SQLite is used. Do not change that
claim until events are stored in an append-only or WORM-capable ledger and hash-chain/signature
verification is actually implemented and tested.

The optional MCP stdio server is intended for local host integration. If it is
converted to Streamable HTTP, configure the official SDK's OAuth resource-server
support and replace model-controlled tenant/role tool arguments with verified
identity claims before exposing it to a network.

## 4. Required production replacements

Before handling non-demo data, place the API behind a gateway that terminates TLS, validates OIDC/JWT tokens and injects trusted tenant/user/role claims. Apply distributed rate limits, request size limits and WAF rules there; do not trust `X-Forwarded-For` unless the gateway strips and recreates it. Replace SQLite with a managed transactional store and use Qdrant/Postgres with tenant filters enforced server-side. Send audit events to immutable or WORM-capable storage and export privacy-safe metrics/traces to your monitoring platform.

Also add malware/archive-bomb scanning before document parsing, enterprise DLP before ingestion, KMS-managed encryption, secret rotation, rate limits, idempotency for write requests, backup/restore drills, deletion/legal-hold workflows and red-team tests for prompt injection and data exfiltration.

## 5. Go-live evidence

Keep a release record containing the image digest, dependency scan, configuration review, approval for every cloud data class, evaluation report, load-test result, restore-drill evidence and alert runbook. Roll out canary-first; alert on egress blocks, citation-verification blocks, authentication errors, sudden abstention changes, zero-result spikes, cross-tenant denial anomalies and benchmark regressions.

See [SECURITY.md](SECURITY.md) and [OBSERVABILITY.md](OBSERVABILITY.md) for the current control boundary and remaining gaps.
