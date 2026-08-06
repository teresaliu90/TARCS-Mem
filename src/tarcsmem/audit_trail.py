"""Public contracts for privacy-safe, answer-centric audit trails.

The reference service persists answer, evidence-pack and finalization events in
SQLite and exposes them through an access-aware HTTP endpoint. SQLite is not an
immutable or tamper-evident ledger; production deployments should replace that
storage boundary while preserving these public response types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from .models import AccessContext


@dataclass(frozen=True, slots=True)
class PolicyVersionRef:
    """Immutable reference to the exact policy evaluated for a decision."""

    policy_id: str
    version: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class AnswerEvidenceLineage:
    """Selection and write-lineage references for one governed memory."""

    memory_id: str
    source_ref: str
    classification: str
    valid_from: date | None
    valid_to: date | None
    selected_reason_codes: tuple[str, ...]
    scores: dict[str, float]
    write_event_ids: tuple[str, ...]
    approval_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "source_ref": self.source_ref,
            "classification": self.classification,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "selected_reason_codes": list(self.selected_reason_codes),
            "scores": dict(self.scores),
            "write_event_ids": list(self.write_event_ids),
            "approval_event_ids": list(self.approval_event_ids),
        }


@dataclass(frozen=True, slots=True)
class AnswerAuditTrail:
    """Privacy-safe, answer-centric evidence-chain response contract."""

    answer_id: str
    evidence_pack_id: str
    correlation_id: str
    outcome: str
    created_at: datetime
    as_of: date
    query_hash: str
    principal_snapshot_hash: str
    query_event_id: str
    evidence_pack_event_id: str
    selected_evidence: tuple[AnswerEvidenceLineage, ...]
    excluded_summary: dict[str, int]
    policy_versions: dict[str, PolicyVersionRef]
    verification: dict[str, str]
    integrity: dict[str, Any]
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation with no raw question text."""

        return {
            "answer_id": self.answer_id,
            "evidence_pack_id": self.evidence_pack_id,
            "correlation_id": self.correlation_id,
            "outcome": self.outcome,
            "created_at": self.created_at.isoformat(),
            "as_of": self.as_of.isoformat(),
            "query_hash": self.query_hash,
            "principal_snapshot_hash": self.principal_snapshot_hash,
            "query_event_id": self.query_event_id,
            "evidence_pack_event_id": self.evidence_pack_event_id,
            "selected_evidence": [item.to_dict() for item in self.selected_evidence],
            "excluded_summary": dict(self.excluded_summary),
            "policy_versions": {
                name: policy.to_dict() for name, policy in self.policy_versions.items()
            },
            "verification": dict(self.verification),
            "integrity": dict(self.integrity),
            "trace_id": self.trace_id,
        }


@runtime_checkable
class AnswerAuditTrailReader(Protocol):
    """Storage-neutral query boundary for the answer audit endpoint.

    A concrete reader must authorize ``access`` before returning tenant-scoped
    metadata. Evidence content remains excluded unless an independently verified
    caller is allowed to request it.
    """

    def get_answer_audit_trail(
        self,
        answer_id: str,
        access: AccessContext,
        *,
        include_evidence_content: bool = False,
    ) -> AnswerAuditTrail | None:
        """Return the answer evidence chain, or ``None`` when it is not found."""

        ...


__all__ = [
    "AnswerAuditTrail",
    "AnswerAuditTrailReader",
    "AnswerEvidenceLineage",
    "PolicyVersionRef",
]
