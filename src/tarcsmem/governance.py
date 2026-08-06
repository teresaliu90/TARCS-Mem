from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import MemoryRecord, MemoryStatus, SourceType

SOURCE_MINIMUMS: dict[SourceType, tuple[float, float, MemoryStatus]] = {
    SourceType.OFFICIAL_POLICY: (0.75, 0.70, MemoryStatus.VERIFIED_ACTIVE),
    SourceType.APPROVED_EXCEPTION: (0.80, 0.70, MemoryStatus.VERIFIED_ACTIVE),
    SourceType.SYSTEM_RECORD: (0.75, 0.75, MemoryStatus.VERIFIED_ACTIVE),
    # A benchmark corpus has traceable provenance but is not an authoritative
    # company policy. Keep its authority lower than official business sources.
    SourceType.PUBLIC_DATASET: (0.45, 0.50, MemoryStatus.VERIFIED_ACTIVE),
    SourceType.MEETING_NOTE: (0.65, 0.65, MemoryStatus.PENDING),
    SourceType.USER_CLAIM: (0.80, 0.80, MemoryStatus.PENDING),
    SourceType.MODEL_INFERENCE: (1.01, 1.01, MemoryStatus.REJECTED),
}


@dataclass(slots=True)
class AdmissionDecision:
    status: MemoryStatus
    reasons: list[str]


class MemoryAdmission:
    """GuardWrite: an explainable write policy, not a model self-confidence score."""

    def decide(self, record: MemoryRecord) -> AdmissionDecision:
        min_confidence, min_durable, success_status = SOURCE_MINIMUMS[record.source_type]
        reasons: list[str] = []
        if record.source_type is SourceType.MODEL_INFERENCE:
            return AdmissionDecision(
                MemoryStatus.REJECTED, ["model inference cannot become fact memory"]
            )
        if not record.evidence:
            return AdmissionDecision(MemoryStatus.PENDING, ["missing traceable evidence"])
        if record.extraction_confidence < min_confidence:
            return AdmissionDecision(
                MemoryStatus.PENDING, ["extraction confidence below source threshold"]
            )
        if record.durable_value < min_durable:
            return AdmissionDecision(
                MemoryStatus.REJECTED, ["not durable enough for long-term memory"]
            )
        if success_status is MemoryStatus.PENDING:
            return AdmissionDecision(
                MemoryStatus.PENDING, ["source requires confirmation before activation"]
            )
        reasons.append("source, evidence and durability passed admission thresholds")
        return AdmissionDecision(success_status, reasons)


def intervals_overlap(left: MemoryRecord, right: MemoryRecord) -> bool:
    left_start = left.valid_from or date.min
    left_end = left.valid_to or date.max
    right_start = right.valid_from or date.min
    right_end = right.valid_to or date.max
    return left_start <= right_end and right_start <= left_end


@dataclass(slots=True)
class ConflictDecision:
    incoming_status: MemoryStatus
    supersede_ids: list[str]
    reasons: list[str]


class ConflictResolver:
    """Resolves only high-confidence conflicts; ambiguous records remain reviewable."""

    def decide(self, incoming: MemoryRecord, existing: list[MemoryRecord]) -> ConflictDecision:
        active = [
            item
            for item in existing
            if item.status is MemoryStatus.VERIFIED_ACTIVE and intervals_overlap(item, incoming)
        ]
        if not active:
            return ConflictDecision(incoming.status, [], ["no active overlapping conflict"])
        if incoming.status is not MemoryStatus.VERIFIED_ACTIVE:
            return ConflictDecision(
                MemoryStatus.PENDING, [], ["conflicts with active record; review required"]
            )

        supersede_ids: list[str] = []
        for old in active:
            newer = (incoming.valid_from or date.min) >= (old.valid_from or date.min)
            more_authoritative = incoming.authority > old.authority
            same_authority_newer_official = (
                incoming.authority == old.authority
                and incoming.source_type is SourceType.OFFICIAL_POLICY
                and newer
            )
            if more_authoritative or same_authority_newer_official:
                supersede_ids.append(old.id)
            else:
                return ConflictDecision(
                    MemoryStatus.PENDING,
                    [],
                    ["equal or lower authority conflict cannot be auto-resolved"],
                )
        return ConflictDecision(
            MemoryStatus.VERIFIED_ACTIVE,
            supersede_ids,
            ["incoming record is authoritative and newer; active version superseded"],
        )
