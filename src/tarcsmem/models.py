from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class SourceType(StrEnum):
    OFFICIAL_POLICY = "official_policy"
    APPROVED_EXCEPTION = "approved_exception"
    MEETING_NOTE = "meeting_note"
    USER_CLAIM = "user_claim"
    MODEL_INFERENCE = "model_inference"
    SYSTEM_RECORD = "system_record"
    PUBLIC_DATASET = "public_dataset"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    PENDING = "pending"
    VERIFIED_ACTIVE = "verified_active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REJECTED = "rejected"


class EventType(StrEnum):
    INGESTED = "ingested"
    ADMITTED = "admitted"
    STATUS_CHANGED = "status_changed"
    SUPERSEDED = "superseded"
    REVIEWED = "reviewed"
    SECURITY_SCANNED = "security_scanned"
    SECURITY_BLOCKED = "security_blocked"
    CLOUD_EGRESS = "cloud_egress"
    GENERATION_VERIFIED = "generation_verified"
    QUERY = "query"
    EVIDENCE_PACK_CREATED = "evidence_pack_created"
    ANSWER_FINALIZED = "answer_finalized"


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def parse_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        return utcnow()
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(slots=True)
class MemoryRecord:
    fact: str
    source_type: SourceType
    source_ref: str
    authority: float
    conflict_key: str
    id: str = field(default_factory=lambda: str(uuid4()))
    valid_from: date | None = None
    valid_to: date | None = None
    observed_at: datetime = field(default_factory=utcnow)
    evidence: list[str] = field(default_factory=list)
    extraction_confidence: float = 1.0
    durable_value: float = 1.0
    status: MemoryStatus = MemoryStatus.CANDIDATE
    supersedes: str | None = None
    tenant_id: str = "default"
    allowed_roles: list[str] = field(default_factory=list)
    classification: str = "internal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source_type = SourceType(self.source_type)
        self.status = MemoryStatus(self.status)
        self.valid_from = parse_date(self.valid_from)
        self.valid_to = parse_date(self.valid_to)
        self.observed_at = parse_datetime(self.observed_at)
        if not 0 <= self.authority <= 1:
            raise ValueError("authority must be within [0, 1]")
        if not 0 <= self.extraction_confidence <= 1:
            raise ValueError("extraction_confidence must be within [0, 1]")
        if not 0 <= self.durable_value <= 1:
            raise ValueError("durable_value must be within [0, 1]")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        self.tenant_id = self.tenant_id.strip()
        if not self.tenant_id:
            raise ValueError("tenant_id cannot be empty")
        self.allowed_roles = sorted(
            {str(role).strip() for role in self.allowed_roles if str(role).strip()}
        )
        self.classification = self.classification.strip().lower()
        if self.classification not in {"public", "internal", "confidential", "restricted"}:
            raise ValueError("classification must be public, internal, confidential, or restricted")

    def is_valid_at(self, as_of: date) -> bool:
        return (self.valid_from is None or self.valid_from <= as_of) and (
            self.valid_to is None or as_of <= self.valid_to
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source_type"] = self.source_type.value
        result["status"] = self.status.value
        result["valid_from"] = self.valid_from.isoformat() if self.valid_from else None
        result["valid_to"] = self.valid_to.isoformat() if self.valid_to else None
        result["observed_at"] = self.observed_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MemoryRecord:
        return cls(**value)


@dataclass(slots=True)
class AuditEvent:
    event_type: EventType
    record_id: str
    detail: dict[str, Any]
    at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["event_type"] = self.event_type.value
        result["at"] = self.at.isoformat()
        return result


@dataclass(slots=True)
class RankedEvidence:
    record: MemoryRecord
    lexical_score: float
    semantic_score: float
    rrf_score: float
    tarcs_score: float
    token_cost: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.record.id,
            "fact": self.record.fact,
            "source_ref": self.record.source_ref,
            "status": self.record.status.value,
            "scores": {
                "lexical": round(self.lexical_score, 4),
                "semantic": round(self.semantic_score, 4),
                "rrf": round(self.rrf_score, 4),
                "tarcs": round(self.tarcs_score, 4),
            },
            "token_cost": self.token_cost,
            "reasons": self.reasons,
        }


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Authenticated caller attributes used before retrieval and ranking."""

    tenant_id: str = "default"
    roles: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_values(
        cls, tenant_id: str = "default", roles: list[str] | tuple[str, ...] | set[str] | None = None
    ) -> AccessContext:
        normalized_tenant = tenant_id.strip()
        if not normalized_tenant:
            raise ValueError("tenant_id cannot be empty")
        return cls(
            normalized_tenant,
            frozenset(str(role).strip() for role in roles or [] if str(role).strip()),
        )


@dataclass(slots=True)
class QueryResult:
    outcome: str
    answer: str
    citations: list[str]
    selected: list[RankedEvidence]
    excluded: list[dict[str, str]]
    as_of: date
    route: str
    answer_id: str
    evidence_pack_id: str
    correlation_id: str
    trace_id: str | None = None
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "evidence_pack_id": self.evidence_pack_id,
            "correlation_id": self.correlation_id,
            "outcome": self.outcome,
            "answer": self.answer,
            "citations": self.citations,
            "selected_evidence": [item.to_dict() for item in self.selected],
            "decision_trace": {
                "as_of": self.as_of.isoformat(),
                "route": self.route,
                "selected": [item.to_dict() for item in self.selected],
                "excluded": self.excluded,
            },
            "observability": {
                "trace_id": self.trace_id,
                "latency_ms": self.latency_ms,
            },
        }
