from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

from .dataset import synthetic_enterprise_records
from .governance import ConflictResolver, MemoryAdmission, intervals_overlap
from .models import AccessContext, AuditEvent, EventType, MemoryRecord, MemoryStatus, QueryResult
from .observability import Observability
from .retrieval import TARCSRetriever, classify_route
from .security import SecurityGate, SecurityViolation
from .store import SQLiteMemoryStore


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
            self.store.append_event(
                AuditEvent(
                    EventType.QUERY,
                    "query",
                    {
                        "question_hash": self._content_hash(question),
                        "question_length": len(question),
                        "as_of": as_of.isoformat(),
                        "route": route,
                        "outcome": "answered" if meaningful else "abstained",
                    },
                )
            )
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
                )
            root_span.attributes["outcome"] = result.outcome
            root_span.attributes["selected_records"] = len(result.selected)
            trace_id = root_span.trace_id
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

    def audit_trail(self, record_id: str) -> list[dict[str, object]]:
        return self.store.audit_trail(record_id)

    def close(self) -> None:
        self.store.close()
