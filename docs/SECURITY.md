# Security design and deployment notes

## Implemented reference controls

| Risk | Current control | Evidence |
| --- | --- | --- |
| Credentials copied into memory | GuardWrite blocks private keys and common OpenAI, GitHub, AWS and assigned-secret patterns before durable write | `tests/test_security.py` |
| Common PII in memory | Email, Chinese mobile and identity-number patterns are redacted by default | `tests/test_security.py` |
| Cross-tenant retrieval | `tenant_id` is a hard filter before ranking and a Qdrant payload filter | `tests/test_access_control.py` |
| Cross-tenant version collision | conflict resolution is scoped by tenant | `tests/test_access_control.py` |
| Unauthorized documents | `allowed_roles` is checked before scoring; restricted records without an ACL fail closed | `tests/test_access_control.py` |
| Sensitive logs/traces | query audit stores a SHA-256 hash and length; spans contain only allow-listed metadata | `tests/test_observability.py` |
| Unauthenticated local API | optional constant-time bearer-token comparison via `TARCSMEM_API_KEY`; `/healthz` discloses no inventory | `tests/test_api.py` |
| Retry duplicates a memory write | persisted, fingerprint-bound `Idempotency-Key` replay for memory writes and reviews; reuse with a changed body is rejected | `tests/test_api.py` |
| Single-process request flood | direct-peer sliding-window rate limit returns `429` and `Retry-After`; gateway-level distributed limits remain required | `tests/test_api.py` |
| Unsafe approval notes | human-review notes pass through the same security gate before status mutation | `tests/test_security.py` |
| Cloud model credential leakage | DeepSeek key is environment-only and excluded from payloads, metrics and errors; authentication failures are tested without a live key | `tests/test_deepseek.py` |
| Confidential evidence sent to a cloud model | A final egress gate blocks cloud generation unless every selected record classification is explicitly allow-listed; block/allow events are audited and metered | `tests/test_agent.py` |
| LLM invents or omits source citations | Generated output is blocked unless it contains at least one exact `[SOURCE: ...]` label drawn from the governed evidence pack | `tests/test_agent.py` |
| MCP agent promotes its own output to policy | MCP proposals have server-fixed `user_claim` source type and low authority, and therefore require human review | `tests/test_mcp.py` |
| Compatible client replaces governance with a system prompt | Client system messages are ignored; the server builds the only authoritative evidence/citation/egress prompt | `tests/test_api.py` |

`TARCSMEM_SECURITY_MODE=redact` is the safe default. `reject` blocks any finding, `audit` is development-only, and `off` is only appropriate when an external DLP gate is guaranteed.

## Security boundaries

- Treat all documents and chat content as untrusted input. Do not let retrieved instructions override system policy.
- Validate ingestion into a strict schema; do not execute text from a memory record.
- Enforce document ACLs before retrieval, not after model generation. TARCS-Mem does this in the reference retrieval path.
- Separate tenant IDs at storage, conflict resolution and query layers. The reference store filters tenant-aware conflicts; production databases should also enforce row-level security or physically separate tenants.
- Encrypt data in transit and at rest; store provider keys only in a secret manager.
- Use `/healthz` only for liveness and protect `/readyz` with service authentication. Propagate its response `X-Request-ID` through the gateway and SIEM, never raw query text.
- Redact PII and secrets before traces, evaluation artifacts and Git commits.
- Require human approval for pending conflicts and sensitive policy activation.
- Treat cloud inference as an explicit data-egress boundary: approve the provider and data class, minimize selected evidence, use provider retention controls, and keep restricted data local unless policy permits otherwise. `TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS` defaults to `public,internal`; it is enforced immediately before cloud generation rather than merely documented.
- Keep `TARCSMEM_REQUIRE_GENERATION_CITATIONS=true` for all governed-answer paths. This reference verifies source-label presence and membership, not whether every atomic statement is entailed; high-risk workflows still need claim-level verification.

## Production enterprise architecture

1. Terminate TLS at a trusted gateway and validate OIDC/JWT issuer, audience, expiry and signature.
2. Derive `tenant_id`, user ID and roles from verified claims. Never accept them from a public request body as the authority source.
3. Evaluate authorization through Casbin or OPA and push tenant/document filters into Qdrant/Postgres before vector scoring.
4. Replace the regex reference detector with enterprise DLP/Presidio plus custom Chinese entities; scan uploads for malware and archive bombs before parsing.
5. Encrypt volumes and backups with KMS-managed keys; rotate service credentials through a secret manager.
6. Export security events and privacy-safe traces to SIEM/OpenTelemetry/Phoenix with retention limits and tenant-safe dashboards.
7. Add rate limits, idempotency keys, deletion/legal-hold workflows, backup restoration drills and prompt-injection/data-exfiltration red-team suites.
8. Make cloud egress approval a change-controlled policy: bind data classes to approved providers, regions and retention terms; keep `confidential` and `restricted` local unless a security owner approves an exception.

## Explicit limitations

- The built-in detector is deterministic and dependency-light; it will have false positives and false negatives.
- Bearer authentication is a local deployment baseline, not full user identity or fine-grained authorization.
- API `roles` and `tenant_id` fields make the local demo testable but are spoofable unless an authenticated gateway replaces them with verified claims.
- MCP tool `roles` and `tenant_id` arguments have the same limitation. Use MCP OAuth/verified host identity before exposing an HTTP transport.
- SQLite stores tenants together and has no encryption or database row-level security.
- Audit events are append-oriented, not cryptographically immutable or externally notarized.

## Operations

Before production, define SLOs for query availability, P95 latency, abstention drift, ACL denials and ingestion failures. Alert on credential blocks, sudden zero-result rates, tenant-boundary denials and evaluation regressions. Do not attach raw questions or documents to alerts.

The repository intentionally omits all customer data, API keys and company-specific business rules.
