# Answer Audit Trail API

Status: **implemented reference API; suitable for local evaluation and bounded pilots**

TARCS-Mem assigns stable `answer_id`, `evidence_pack_id` and `correlation_id` values to every
governed query. Privacy-safe events connect the answer to the selected memory versions, write
lineage, exclusion summary, policy references and final verification result. The API deliberately
omits raw question text and evidence content.

The current implementation uses the reference SQLite event store. It does **not** claim immutable,
WORM or cryptographically verified ledger integrity. Production deployments should replace the
storage and identity boundaries while preserving the public response contract.

## Public contract

The response types live in `src/tarcsmem/audit_trail.py`:

- `AnswerAuditTrail` — the top-level privacy-safe answer evidence chain;
- `AnswerEvidenceLineage` — one selected memory and its write/approval event references;
- `PolicyVersionRef` — the policy ID, version and digest used by the decision;
- `AnswerAuditTrailReader` — the storage-neutral, access-aware query protocol.

The service boundary is:

```python
get_answer_audit_trail(
    answer_id: str,
    access: AccessContext,
    *,
    include_evidence_content: bool = False,
) -> AnswerAuditTrail | None
```

Content expansion is intentionally unsupported. `access` is required because source references,
exclusion counts and policy metadata can still be sensitive. The reference reader requires the
same tenant and rechecks every selected record against its current ACL and the original business
date. If any selected record is no longer visible, the complete answer trail is hidden rather than
returning a partial or existence-revealing response.

## HTTP endpoint

```http
GET /v1/answers/{answer_id}/audit?tenant_id=default&roles=finance
```

Malformed, unknown and unauthorized IDs all return the same `404` response. This prevents the
endpoint from becoming a cross-tenant answer-existence oracle. When API-key authentication is
enabled, the same Bearer token used by the rest of the API is required.

`tenant_id` and `roles` query parameters exist only for the local reference deployment. They are
not trustworthy identity claims. A production gateway must validate OIDC/JWT credentials and bind
server-side tenant and role claims before constructing `AccessContext`.

Example response (values abbreviated for readability):

```json
{
  "answer_id": "ans_9ccfa4ee837f4ff291a628aa67b5d3e9",
  "evidence_pack_id": "pack_52efaf5dbcb44fdf99081c2382599cf1",
  "correlation_id": "corr_82a9ff747c0e412cac475351bb5fdb21",
  "outcome": "answered",
  "created_at": "2026-08-06T10:30:00+00:00",
  "as_of": "2026-08-15",
  "query_hash": "sha256:5c4b…",
  "principal_snapshot_hash": "sha256:86bb…",
  "query_event_id": "d12e7e90-…",
  "evidence_pack_event_id": "a34f3165-…",
  "selected_evidence": [
    {
      "memory_id": "memory-001",
      "source_ref": "POLICY-SALES-2026-07#1",
      "classification": "internal",
      "valid_from": "2026-07-01",
      "valid_to": null,
      "selected_reason_codes": [
        "ACTIVE_AT_AS_OF",
        "ACCESS_ALLOWED",
        "RELEVANCE_ABOVE_FLOOR",
        "SELECTED_BY_CONSTRAINED_MMR"
      ],
      "scores": {"rrf": 1.0, "tarcs": 0.8654},
      "write_event_ids": ["b2830f6e-…", "82ce4109-…"],
      "approval_event_ids": []
    }
  ],
  "excluded_summary": {
    "low_relevance": 1,
    "outside_business_time": 1,
    "status_ineligible": 3
  },
  "policy_versions": {
    "governance": {
      "policy_id": "builtin-tarcs-governance",
      "version": "0.8.0",
      "digest": "sha256:9ce1…"
    }
  },
  "verification": {
    "retrieval": "passed",
    "citation_membership": "passed"
  },
  "integrity": {
    "chain_verified": false,
    "mode": "sqlite_reference_store"
  },
  "trace_id": "aa6e54ab8d2c4df7…"
}
```

## Event flow

One query writes three privacy-safe event classes under the stable `answer_id`:

1. `query` stores the IDs, tenant, principal snapshot hash, question hash/length, business date,
   route and trace ID.
2. `evidence_pack_created` stores selected memory lineage, reason codes, scores, aggregate
   exclusions, policy references and the explicit storage-integrity mode.
3. `answer_finalized` stores the final outcome, execution phase, provider name when applicable and
   verification statuses. A generated or blocked answer can append a later finalization event; the
   reader returns the latest one.

The raw question, memory text, prompts, credentials and tokens are excluded from these events.
The API rehydrates only safe metadata and reauthorizes selected memory references at read time.

## Console flow

The governance console turns the contract into a three-step first-run path:

1. confirm that the six synthetic records are loaded;
2. run the policy-version governed query;
3. select **查看回答证据链** to inspect selected evidence, exclusions, policy reference,
   verification results, lineage IDs and the SQLite integrity limitation.

This path requires no model API key, model download or vector database.

## Verified behavior

The automated suite covers:

- stable IDs across the service, native query API and OpenAI-compatible response;
- selected evidence and exact write-lineage references;
- latest finalization outcome after generation, citation failure or egress blocking;
- same-tenant enforcement and current ACL/role rechecks at the original business date;
- indistinguishable `404` responses for malformed, unknown and unauthorized answer IDs;
- omission of raw question and evidence content;
- explicit `chain_verified: false` for the SQLite reference store.

## Production hardening still required

- derive `AccessContext` only from verified OIDC/SSO claims, not request parameters;
- move events to append-only or WORM-capable storage with retention and legal-hold controls;
- add hash-chain/signature verification and key rotation before reporting `chain_verified: true`;
- define SIEM export, backup/restore, deletion, incident and audit-access procedures;
- authorize any future evidence-content expansion separately from metadata access;
- load-test tenant/ACL rechecks and add database-level tenant isolation.
