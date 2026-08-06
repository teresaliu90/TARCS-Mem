from __future__ import annotations

import hashlib
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from .audit_trail import AnswerAuditTrail, AnswerEvidenceLineage, PolicyVersionRef
from .dataset import synthetic_enterprise_records
from .governance import ConflictResolver, MemoryAdmission, intervals_overlap
from .models import (
    AccessContext,
    AuditEvent,
    EventType,
    MemoryRecord,
    MemoryStatus,
    QueryResult,
    RankedEvidence,
)
from .observability import Observability
from .retrieval import TARCSRetriever, classify_route
from .security import SecurityGate, SecurityViolation
from .store import SQLiteMemoryStore

_POLICY_ID = "builtin-tarcs-governance"
_POLICY_VERSION = "0.8.0"
_POLICY_DIGEST = (
    "sha256:"
    + hashlib.sha256(b"tarcsmem:0.8.0:MemoryAdmission:ConflictResolver:TARCSRetriever").hexdigest()
)


class TARCSMemoryService:
    def __init__(
        self,
        db_path: str | Path = ":memory:",
        security_gate: SecurityGate | None = None,
        observability: Observability | None = None,
    ) -> None:
        self.store = SQLiteMemoryStore(db_path)
        self.admission = MemoryAdmission()
        self.conflicts = ConflictResolver()
        self.retriever = TARCSRetriever()
        self.security = security_gate or SecurityGate.from_environment()
        self.observability = observability or Observability()

    @staticmethod
    def _content_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @classmethod
    def _principal_snapshot_hash(cls, access: AccessContext) -> str:
        canonical = f"{access.tenant_id}:{','.join(sorted(access.roles))}"
        return f"sha256:{cls._content_hash(canonical)}"

    @staticmethod
    def _exclusion_code(reason: str) -> str:
        if "tenant boundary" in reason:
            return "tenant_denied"
        if "restricted ACL missing" in reason:
            return "restricted_acl_missing"
        if "role not allowed" in reason:
            return "role_denied"
        if "status=" in reason:
            return "status_ineligible"
        if "valid-time" in reason:
            return "outside_business_time"
        if "relevance" in reason:
            return "low_relevance"
        return "other"

    @staticmethod
    def _selection_reason_codes(item: RankedEvidence) -> list[str]:
        codes = ["ACTIVE_AT_AS_OF", "ACCESS_ALLOWED", "RELEVANCE_ABOVE_FLOOR"]
        if item.record.status is MemoryStatus.SUPERSEDED:
            codes[0] = "HISTORICAL_VERSION_AT_AS_OF"
        if any("MMR=" in reason for reason in item.reasons):
            codes.append("SELECTED_BY_CONSTRAINED_MMR")
        return codes

    def _evidence_lineage_payload(self, item: RankedEvidence) -> dict[str, Any]:
        history = self.store.audit_trail(item.record.id)
        approval_event_ids = [
            str(event["id"]) for event in history if event["event_type"] == EventType.REVIEWED.value
        ]
        write_event_ids = [
            str(event["id"]) for event in history if event["event_type"] != EventType.REVIEWED.value
        ]
        return {
            "memory_id": item.record.id,
            "source_ref": item.record.source_ref,
            "classification": item.record.classification,
            "valid_from": item.record.valid_from.isoformat() if item.record.valid_from else None,
            "valid_to": item.record.valid_to.isoformat() if item.record.valid_to else None,
            "selected_reason_codes": self._selection_reason_codes(item),
            "scores": {
                "lexical": round(item.lexical_score, 4),
                "semantic": round(item.semantic_score, 4),
                "rrf": round(item.rrf_score, 4),
                "tarcs": round(item.tarcs_score, 4),
            },
            "write_event_ids": write_event_ids,
            "approval_event_ids": approval_event_ids,
            "supersedes_memory_id": item.record.supersedes,
        }

    @staticmethod
    def _policy_payload() -> dict[str, dict[str, str]]:
        return {
            "governance": {
                "policy_id": _POLICY_ID,
                "version": _POLICY_VERSION,
                "digest": _POLICY_DIGEST,
            }
        }

    def ingest(self, record: MemoryRecord) -> MemoryRecord:
        labels = {"source_type": record.source_type.value}
        with self.observability.tracer.span(
            "tarcsmem.guardwrite",
            {
                "source_type": record.source_type.value,
                "classification": record.classification,
                "tenant_scoped": record.tenant_id != "default",
            },
        ) as span:
            security = self.security.evaluate(record.fact)
            security_detail = {
                "mode": self.security.mode,
                "finding_counts": security.counts,
                "redacted": security.redacted,
                "allowed": security.allowed,
            }
            self.store.append_event(
                AuditEvent(EventType.SECURITY_SCANNED, record.id, security_detail)
            )
            for category, count in security.counts.items():
                self.observability.metrics.increment(
                    "tarcsmem_security_findings_total",
                    count,
                    {"category": category},
                )
            if not security.allowed:
                self.store.append_event(
                    AuditEvent(
                        EventType.SECURITY_BLOCKED,
                        record.id,
                        {"reason": security.reason, "finding_counts": security.counts},
                    )
                )
                self.observability.metrics.increment(
                    "tarcsmem_ingest_total", labels={**labels, "outcome": "blocked"}
                )
                span.attributes["outcome"] = "blocked"
                raise SecurityViolation(
                    f"ingestion blocked by security gate ({sum(security.counts.values())} finding(s))"
                )
            if security.redacted:
                record.fact = security.text
                record.metadata = {
                    **record.metadata,
                    "security": {
                        "redacted": True,
                        "finding_counts": security.counts,
                    },
                }

            self.store.append_event(
                AuditEvent(
                    EventType.INGESTED,
                    record.id,
                    {"source_ref_hash": self._content_hash(record.source_ref)},
                )
            )
            admission = self.admission.decide(record)
            record.status = admission.status
            self.store.append_event(
                AuditEvent(
                    EventType.ADMITTED,
                    record.id,
                    {"status": record.status.value, "reasons": admission.reasons},
                )
            )
            conflict = self.conflicts.decide(
                record, self.store.by_conflict_key(record.conflict_key, record.tenant_id)
            )
            record.status = conflict.incoming_status
            for old_id in conflict.supersede_ids:
                old = self.store.get(old_id)
                if old:
                    old.status = MemoryStatus.SUPERSEDED
                    # Preserve the historical projection. The old version must remain
                    # answerable for a business date before the replacement took effect.
                    if record.valid_from and (
                        old.valid_to is None or old.valid_to >= record.valid_from
                    ):
                        old.valid_to = record.valid_from - timedelta(days=1)
                    self.store.save(old)
                    self.store.append_event(
                        AuditEvent(
                            EventType.SUPERSEDED,
                            old.id,
                            {"by": record.id, "reason": conflict.reasons},
                        )
                    )
                    record.supersedes = old.id
            self.store.save(record)
            self.store.append_event(
                AuditEvent(
                    EventType.STATUS_CHANGED,
                    record.id,
                    {"status": record.status.value, "reasons": conflict.reasons},
                )
            )
            self.observability.metrics.increment(
                "tarcsmem_ingest_total", labels={**labels, "outcome": record.status.value}
            )
            span.attributes["outcome"] = record.status.value
        return record

    def seed(self, if_empty: bool = False) -> int:
        if if_empty and self.store.count():
            return 0
        if self.store.count():
            raise ValueError("store is not empty; pass --if-empty or use a new database")
        for record in synthetic_enterprise_records():
            self.ingest(record)
        return self.store.count()

    def query(
        self,
        question: str,
        as_of: date,
        access: AccessContext | None = None,
    ) -> QueryResult:
        return self.query_records(question, as_of, self.store.list_all(), access)

    def review(
        self,
        record_id: str,
        decision: str,
        reviewer: str,
        note: str = "",
    ) -> MemoryRecord:
        """Apply a traceable human decision to a pending memory.

        Human review can activate a pending source, but it cannot silently weaken
        an existing active policy. An overlapping record must have a business
        effective date and strictly higher authority before it can supersede the
        current active version.
        """
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")
        reviewer = reviewer.strip()
        if not reviewer:
            raise ValueError("reviewer is required for an auditable decision")

        record = self.store.get(record_id)
        if record is None:
            raise ValueError("memory record not found")
        if record.status is not MemoryStatus.PENDING:
            raise ValueError("only pending memories can be reviewed")

        note_decision = self.security.evaluate(note.strip())
        if not note_decision.allowed:
            self.observability.metrics.increment(
                "tarcsmem_reviews_total", labels={"decision": normalized, "outcome": "blocked"}
            )
            raise SecurityViolation("review note blocked by security gate")
        safe_note = note_decision.text

        with self.observability.tracer.span(
            "tarcsmem.review", {"decision": normalized, "note_redacted": note_decision.redacted}
        ) as span:
            previous_status = record.status.value
            superseded_ids: list[str] = []
            if normalized == "reject":
                record.status = MemoryStatus.REJECTED
            else:
                if not record.evidence:
                    raise ValueError("a pending memory needs traceable evidence before approval")
                active_conflicts = [
                    item
                    for item in self.store.by_conflict_key(record.conflict_key, record.tenant_id)
                    if item.id != record.id
                    and item.status is MemoryStatus.VERIFIED_ACTIVE
                    and intervals_overlap(item, record)
                ]
                if active_conflicts and record.valid_from is None:
                    raise ValueError(
                        "an overlapping approval needs valid_from so the prior version can be closed"
                    )
                weaker = [item for item in active_conflicts if record.authority <= item.authority]
                if weaker:
                    refs = ", ".join(item.source_ref for item in weaker)
                    raise ValueError(
                        "approval would weaken an active source; reject it or ingest a more "
                        f"authoritative record first ({refs})"
                    )
                for old in active_conflicts:
                    old.status = MemoryStatus.SUPERSEDED
                    if record.valid_from and (
                        old.valid_to is None or old.valid_to >= record.valid_from
                    ):
                        old.valid_to = record.valid_from - timedelta(days=1)
                    self.store.save(old)
                    self.store.append_event(
                        AuditEvent(
                            EventType.SUPERSEDED,
                            old.id,
                            {"by": record.id, "reason": "human-approved higher-authority version"},
                        )
                    )
                    superseded_ids.append(old.id)
                record.status = MemoryStatus.VERIFIED_ACTIVE
                if superseded_ids:
                    record.supersedes = superseded_ids[0]

            self.store.save(record)
            detail = {
                "decision": normalized,
                "reviewer": reviewer,
                "note": safe_note,
                "note_redacted": note_decision.redacted,
                "from_status": previous_status,
                "to_status": record.status.value,
                "superseded_ids": superseded_ids,
            }
            self.store.append_event(AuditEvent(EventType.REVIEWED, record.id, detail))
            self.store.append_event(
                AuditEvent(
                    EventType.STATUS_CHANGED,
                    record.id,
                    {"status": record.status.value, "reason": "human review"},
                )
            )
            span.attributes["outcome"] = record.status.value
        self.observability.metrics.increment(
            "tarcsmem_reviews_total", labels={"decision": normalized, "outcome": "completed"}
        )
        return record

    def query_records(
        self,
        question: str,
        as_of: date,
        records: list[MemoryRecord],
        access: AccessContext | None = None,
    ) -> QueryResult:
        """Answer using a pre-filtered candidate set from a vector store or tool."""
        access = access or AccessContext()
        answer_id = self._public_id("ans")
        evidence_pack_id = self._public_id("pack")
        correlation_id = self._public_id("corr")
        route = classify_route(question)
        started = perf_counter()
        with self.observability.tracer.span(
            "tarcsmem.query",
            {
                "route": route,
                "question_length": len(question),
                "roles_count": len(access.roles),
                "tenant_scoped": access.tenant_id != "default",
            },
        ) as root_span:
            with self.observability.tracer.span(
                "tarcsmem.guardread.rank", {"candidate_records": len(records)}
            ) as rank_span:
                candidates, excluded = self.retriever.rank(question, records, as_of, access)
                rank_span.attributes["ranked_records"] = len(candidates)
                rank_span.attributes["excluded_records"] = len(excluded)
            with self.observability.tracer.span(
                "tarcsmem.guardread.select", {"ranked_records": len(candidates)}
            ) as select_span:
                # Apply the relevance floor before budgeted MMR. Otherwise an
                # authoritative but unrelated record can consume the context
                # budget before a grounded candidate is considered.
                relevant, irrelevant = self.retriever.relevant_candidates(candidates)
                excluded.extend(irrelevant)
                meaningful = self.retriever.select(question, relevant)
                select_span.attributes["relevant_records"] = len(relevant)
                select_span.attributes["selected_records"] = len(meaningful)
            if not meaningful:
                result = QueryResult(
                    outcome="abstained",
                    answer=(
                        "I cannot provide a grounded answer because no active, valid, "
                        "traceable evidence was selected."
                    ),
                    citations=[],
                    selected=[],
                    excluded=excluded,
                    as_of=as_of,
                    route=route,
                    answer_id=answer_id,
                    evidence_pack_id=evidence_pack_id,
                    correlation_id=correlation_id,
                )
            else:
                facts = " ".join(item.record.fact for item in meaningful)
                result = QueryResult(
                    outcome="answered",
                    answer=f"Based on {len(meaningful)} governed evidence record(s): {facts}",
                    citations=[item.record.source_ref for item in meaningful],
                    selected=meaningful,
                    excluded=excluded,
                    as_of=as_of,
                    route=route,
                    answer_id=answer_id,
                    evidence_pack_id=evidence_pack_id,
                    correlation_id=correlation_id,
                )
            root_span.attributes["outcome"] = result.outcome
            root_span.attributes["selected_records"] = len(result.selected)
            root_span.attributes["answer_id"] = answer_id
            root_span.attributes["evidence_pack_id"] = evidence_pack_id
            root_span.attributes["correlation_id"] = correlation_id
            trace_id = root_span.trace_id
            query_event = AuditEvent(
                EventType.QUERY,
                answer_id,
                {
                    "answer_id": answer_id,
                    "evidence_pack_id": evidence_pack_id,
                    "correlation_id": correlation_id,
                    "tenant_id": access.tenant_id,
                    "principal_snapshot_hash": self._principal_snapshot_hash(access),
                    "question_hash": f"sha256:{self._content_hash(question)}",
                    "question_length": len(question),
                    "as_of": as_of.isoformat(),
                    "route": route,
                    "trace_id": trace_id,
                },
            )
            self.store.append_event(query_event)
            exclusion_summary = Counter(
                self._exclusion_code(item["reason"]) for item in result.excluded
            )
            evidence_event = AuditEvent(
                EventType.EVIDENCE_PACK_CREATED,
                answer_id,
                {
                    "answer_id": answer_id,
                    "evidence_pack_id": evidence_pack_id,
                    "correlation_id": correlation_id,
                    "selected_evidence": [
                        self._evidence_lineage_payload(item) for item in result.selected
                    ],
                    "excluded_summary": dict(exclusion_summary),
                    "policy_versions": self._policy_payload(),
                    "integrity": {
                        "chain_verified": False,
                        "mode": "sqlite_reference_store",
                    },
                },
            )
            self.store.append_event(evidence_event)
            self.record_answer_finalization(
                answer_id,
                correlation_id,
                result.outcome,
                phase="retrieval",
                verification={
                    "retrieval": "passed" if meaningful else "no_eligible_evidence",
                    "citation_membership": "passed" if meaningful else "not_applicable",
                },
            )
        latency_ms = round((perf_counter() - started) * 1_000, 3)
        result.trace_id = trace_id
        result.latency_ms = latency_ms
        self.observability.metrics.increment(
            "tarcsmem_queries_total", labels={"outcome": result.outcome, "route": route}
        )
        self.observability.metrics.observe(
            "tarcsmem_query_duration_ms", latency_ms, {"route": route}
        )
        self.observability.metrics.observe(
            "tarcsmem_selected_records", len(result.selected), {"outcome": result.outcome}
        )
        return result

    def record_answer_finalization(
        self,
        answer_id: str,
        correlation_id: str,
        outcome: str,
        *,
        phase: str,
        verification: dict[str, str],
        provider: str | None = None,
    ) -> str:
        """Append a privacy-safe finalization event and return its event ID."""

        event = AuditEvent(
            EventType.ANSWER_FINALIZED,
            answer_id,
            {
                "answer_id": answer_id,
                "correlation_id": correlation_id,
                "outcome": outcome,
                "phase": phase,
                "verification": verification,
                "provider": provider,
            },
        )
        self.store.append_event(event)
        return event.id

    def get_answer_audit_trail(
        self,
        answer_id: str,
        access: AccessContext,
        *,
        include_evidence_content: bool = False,
    ) -> AnswerAuditTrail | None:
        """Return an authorized answer evidence chain from privacy-safe events.

        The reference implementation permits same-tenant reads and re-applies
        current record ACLs at the original business date. Production deployments
        must additionally bind ``access`` to verified identity claims.
        """

        if include_evidence_content:
            raise ValueError("evidence content expansion is not implemented")
        events = self.store.audit_trail(answer_id)
        query_event = next(
            (event for event in events if event["event_type"] == EventType.QUERY.value), None
        )
        evidence_event = next(
            (
                event
                for event in events
                if event["event_type"] == EventType.EVIDENCE_PACK_CREATED.value
            ),
            None,
        )
        final_events = [
            event for event in events if event["event_type"] == EventType.ANSWER_FINALIZED.value
        ]
        if query_event is None or evidence_event is None or not final_events:
            return None

        query_detail = dict(query_event["detail"])
        evidence_detail = dict(evidence_event["detail"])
        if query_detail.get("tenant_id") != access.tenant_id:
            return None
        as_of = date.fromisoformat(str(query_detail["as_of"]))
        selected_payloads = list(evidence_detail.get("selected_evidence", []))
        selected: list[AnswerEvidenceLineage] = []
        for raw_item in selected_payloads:
            item = dict(raw_item)
            record = self.store.get(str(item["memory_id"]))
            if record is None:
                return None
            eligible, _ = self.retriever.filter_records([record], as_of, access)
            if not eligible:
                return None
            selected.append(
                AnswerEvidenceLineage(
                    memory_id=str(item["memory_id"]),
                    source_ref=str(item["source_ref"]),
                    classification=str(item["classification"]),
                    valid_from=(
                        date.fromisoformat(str(item["valid_from"]))
                        if item.get("valid_from")
                        else None
                    ),
                    valid_to=(
                        date.fromisoformat(str(item["valid_to"])) if item.get("valid_to") else None
                    ),
                    selected_reason_codes=tuple(item.get("selected_reason_codes", [])),
                    scores={
                        str(name): float(value)
                        for name, value in dict(item.get("scores", {})).items()
                    },
                    write_event_ids=tuple(item.get("write_event_ids", [])),
                    approval_event_ids=tuple(item.get("approval_event_ids", [])),
                    supersedes_memory_id=(
                        str(item["supersedes_memory_id"])
                        if item.get("supersedes_memory_id")
                        else None
                    ),
                )
            )

        policy_versions = {
            str(name): PolicyVersionRef(
                policy_id=str(value["policy_id"]),
                version=str(value["version"]),
                digest=str(value["digest"]),
            )
            for name, value in dict(evidence_detail.get("policy_versions", {})).items()
        }
        final_detail = dict(final_events[-1]["detail"])
        verification = {
            str(name): str(value)
            for name, value in dict(final_detail.get("verification", {})).items()
        }
        return AnswerAuditTrail(
            answer_id=answer_id,
            evidence_pack_id=str(query_detail["evidence_pack_id"]),
            correlation_id=str(query_detail["correlation_id"]),
            outcome=str(final_detail["outcome"]),
            created_at=datetime.fromisoformat(str(query_event["at"])),
            as_of=as_of,
            query_hash=str(query_detail["question_hash"]),
            principal_snapshot_hash=str(query_detail["principal_snapshot_hash"]),
            query_event_id=str(query_event["id"]),
            evidence_pack_event_id=str(evidence_event["id"]),
            selected_evidence=tuple(selected),
            excluded_summary={
                str(name): int(value)
                for name, value in dict(evidence_detail.get("excluded_summary", {})).items()
            },
            policy_versions=policy_versions,
            verification=verification,
            integrity=dict(evidence_detail.get("integrity", {})),
            trace_id=str(query_detail.get("trace_id") or "") or None,
        )

    def audit_trail(self, record_id: str) -> list[dict[str, object]]:
        return self.store.audit_trail(record_id)

    def close(self) -> None:
        self.store.close()
