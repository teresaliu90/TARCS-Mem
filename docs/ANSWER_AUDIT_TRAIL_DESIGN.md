# Answer Audit Trail Contract

Status: **experimental contract stub; persistence and HTTP endpoint are not implemented in v0.8**

The current API exposes audit events by memory record. The next slice adds an answer-centric view
that connects one answer to its evidence pack, selected memory versions, write lineage, policy
versions and verification result.

## Public contract

The experimental types live in `src/tarcsmem/audit_trail.py`:

- `AnswerAuditTrail` — top-level privacy-safe response;
- `AnswerEvidenceLineage` — one selected memory and its write/approval event references;
- `PolicyVersionRef` — exact policy ID, version and digest;
- `AnswerAuditTrailReader` — storage-neutral, access-aware query protocol.

The intended query boundary is:

```python
get_answer_audit_trail(
    answer_id: str,
    access: AccessContext,
    *,
    include_evidence_content: bool = False,
) -> AnswerAuditTrail | None
```

`access` is required because answer metadata, exclusion reasons and source references can still be
sensitive. A request-body tenant or role is not sufficient in production; the endpoint must use a
verified principal derived from the deployment's identity boundary.

## Proposed HTTP endpoint

```http
GET /v1/answers/{answer_id}/audit
```

The endpoint should return `404` for an unknown or non-visible answer so it does not reveal
cross-tenant existence. Content expansion should require a separate permission and remain off by
default.

Example response:

```json
{
  "answer_id": "ans-001",
  "evidence_pack_id": "pack-001",
  "correlation_id": "corr-001",
  "outcome": "answered",
  "created_at": "2026-08-06T10:30:00+00:00",
  "as_of": "2026-08-01",
  "query_hash": "sha256:question",
  "principal_snapshot_hash": "sha256:principal",
  "query_event_id": "evt-query-001",
  "evidence_pack_event_id": "evt-pack-001",
  "selected_evidence": [
    {
      "memory_id": "memory-001",
      "source_ref": "POLICY-2026#1",
      "classification": "internal",
      "valid_from": "2026-01-01",
      "valid_to": null,
      "selected_reason_codes": ["ACTIVE_AT_AS_OF", "ROLE_ALLOWED"],
      "scores": {"rrf": 0.91, "tarcs": 0.88},
      "write_event_ids": ["evt-ingested-001", "evt-admitted-001"],
      "approval_event_ids": []
    }
  ],
  "excluded_summary": {"acl_denied": 2},
  "policy_versions": {
    "governance": {
      "policy_id": "enterprise-policy",
      "version": "2026-08-01",
      "digest": "sha256:policy"
    }
  },
  "verification": {"citation_membership": "passed"},
  "integrity": {"chain_verified": true},
  "trace_id": "trace-001"
}
```

## Implementation sequence

1. Add stable `answer_id`, `evidence_pack_id` and `correlation_id` to the query/generation path.
2. Persist a privacy-safe evidence-pack event containing selected memory/event references and an
   exclusion summary.
3. Implement an SQLite reader that joins answer, evidence-pack and record audit references without
   copying raw questions or memory text into audit events.
4. Add the authenticated endpoint and cross-tenant non-disclosure tests.
5. Add console navigation from a Sandbox result or Trace to this answer-centric view.
6. Replace the reader with an immutable-ledger adapter only after the event schema stabilizes.

## Required tests before endpoint release

- answer IDs remain stable across serialization and API layers;
- selected evidence references the exact memory projection version used;
- excluded details do not leak inaccessible record content;
- unknown and cross-tenant answer IDs are indistinguishable to unauthorized callers;
- missing or unsupported citations are represented as verification failures;
- raw questions, tokens, secrets and document text do not enter the audit response by default;
- duplicate event delivery does not create duplicate evidence lineage.
