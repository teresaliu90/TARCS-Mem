from datetime import date

import pytest

from tarcsmem.models import MemoryRecord, MemoryStatus, SourceType
from tarcsmem.service import TARCSMemoryService


def seeded_service():
    service = TARCSMemoryService()
    service.seed()
    return service


def test_new_official_policy_supersedes_old_version():
    service = seeded_service()
    assert service.store.get("sales-v1").status is MemoryStatus.SUPERSEDED
    assert service.store.get("sales-v2").status is MemoryStatus.VERIFIED_ACTIVE
    service.close()


def test_pending_meeting_note_cannot_pollute_active_memory():
    service = seeded_service()
    assert service.store.get("sales-meeting-note").status is MemoryStatus.PENDING
    service.close()


def test_temporal_authority_selection_uses_latest_active_policy():
    service = seeded_service()
    result = service.query("2026年8月华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result.outcome == "answered"
    assert result.citations == ["POLICY-SALES-2026-07#1"]
    service.close()


def test_historical_query_can_retrieve_superseded_version_in_its_valid_window():
    service = seeded_service()
    result = service.query("2026年5月华南区销售折扣上限是多少？", date(2026, 5, 20))
    assert result.outcome == "answered"
    assert result.citations == ["POLICY-SALES-2026-01#1"]
    service.close()


def test_unsupported_claim_abstains():
    service = seeded_service()
    result = service.query("2026年10月北区培训津贴是否已提高到900元？", date(2026, 10, 2))
    assert result.outcome == "abstained"
    service.close()


def test_human_review_can_activate_a_traceable_pending_memory():
    service = TARCSMemoryService()
    pending = service.ingest(
        MemoryRecord(
            id="reviewable-note",
            fact="华东区复盘模板改为新版。",
            source_type=SourceType.MEETING_NOTE,
            source_ref="MEETING-2026-08#4",
            authority=0.72,
            conflict_key="review-template:华东区",
            evidence=["MEETING-2026-08#4"],
        )
    )
    assert pending.status is MemoryStatus.PENDING

    reviewed = service.review(
        pending.id,
        decision="approve",
        reviewer="reviewer@example.com",
        note="已核对审批工单 GOV-42",
    )

    assert reviewed.status is MemoryStatus.VERIFIED_ACTIVE
    assert service.store.status_counts()["verified_active"] == 1
    events = service.audit_trail(pending.id)
    review_event = next(item for item in events if item["event_type"] == "reviewed")
    assert review_event["detail"]["reviewer"] == "reviewer@example.com"
    service.close()


def test_human_review_rejects_pending_memory_with_audit_note():
    service = seeded_service()
    reviewed = service.review(
        "sales-meeting-note",
        decision="reject",
        reviewer="policy-owner",
        note="与现行正式制度冲突",
    )
    assert reviewed.status is MemoryStatus.REJECTED
    assert service.audit_trail(reviewed.id)[-2]["event_type"] == "reviewed"
    service.close()


def test_human_review_cannot_weaken_an_active_policy():
    service = seeded_service()
    with pytest.raises(ValueError, match="would weaken an active source"):
        service.review(
            "sales-meeting-note",
            decision="approve",
            reviewer="policy-owner",
            note="不能仅凭会议纪要覆盖制度",
        )
    assert service.store.get("sales-meeting-note").status is MemoryStatus.PENDING
    service.close()
