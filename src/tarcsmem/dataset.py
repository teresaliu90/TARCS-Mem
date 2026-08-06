from __future__ import annotations

from datetime import UTC, date, datetime

from .models import MemoryRecord, SourceType


def synthetic_enterprise_records() -> list[MemoryRecord]:
    """Deterministic, fictional records. They contain no customer or employer data."""
    return [
        MemoryRecord(
            id="sales-v1",
            fact="华南区销售折扣上限为8%，自2026-01-01起生效。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="POLICY-SALES-2026-01#1",
            authority=1.0,
            conflict_key="sales_discount_limit:华南区",
            valid_from=date(2026, 1, 1),
            evidence=["synthetic/policy_sales_v1.md#1"],
            observed_at=datetime(2025, 12, 15, tzinfo=UTC),
        ),
        MemoryRecord(
            id="sales-v2",
            fact="华南区销售折扣上限为5%，自2026-07-01起生效。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="POLICY-SALES-2026-07#1",
            authority=1.0,
            conflict_key="sales_discount_limit:华南区",
            valid_from=date(2026, 7, 1),
            evidence=["synthetic/policy_sales_v2.md#1"],
            observed_at=datetime(2026, 6, 20, tzinfo=UTC),
        ),
        MemoryRecord(
            id="sales-meeting-note",
            fact="会议建议华南区折扣维持8%，尚未获批。",
            source_type=SourceType.MEETING_NOTE,
            source_ref="MEETING-2026-06-18#4",
            authority=0.45,
            conflict_key="sales_discount_limit:华南区",
            valid_from=date(2026, 7, 1),
            evidence=["synthetic/meeting_20260618.md#4"],
        ),
        MemoryRecord(
            id="travel-v1",
            fact="差旅住宿报销上限为每晚500元，自2026-01-01起生效。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="POLICY-TRAVEL-2026-01#2",
            authority=1.0,
            conflict_key="travel_hotel_limit:default",
            valid_from=date(2026, 1, 1),
            evidence=["synthetic/travel_v1.md#2"],
        ),
        MemoryRecord(
            id="travel-exception-shenzhen",
            fact="深圳国际展会期间，已审批项目可按每晚800元住宿标准报销，适用于2026-09-10至2026-09-15。",
            source_type=SourceType.APPROVED_EXCEPTION,
            source_ref="APPROVAL-EXPO-SZ-2026#7",
            authority=0.98,
            conflict_key="travel_hotel_limit:shenzhen_expo",
            valid_from=date(2026, 9, 10),
            valid_to=date(2026, 9, 15),
            evidence=["synthetic/approval_expo_sz.md#7"],
        ),
        MemoryRecord(
            id="unverified-claim",
            fact="员工称北区培训津贴已提高到900元，尚未有正式制度。",
            source_type=SourceType.USER_CLAIM,
            source_ref="CHAT-USER-001#3",
            authority=0.20,
            conflict_key="training_allowance:北区",
            valid_from=date(2026, 10, 1),
            evidence=["synthetic/chat_user_001.md#3"],
        ),
    ]


def evaluation_cases() -> list[dict[str, object]]:
    return [
        {
            "name": "new_policy_beats_old_policy",
            "question": "2026年8月华南区销售折扣上限是多少？",
            "as_of": date(2026, 8, 15),
            "expected_outcome": "answered",
            "expected_source": "POLICY-SALES-2026-07#1",
        },
        {
            "name": "historical_policy_query",
            "question": "2026年5月华南区销售折扣上限是多少？",
            "as_of": date(2026, 5, 20),
            "expected_outcome": "answered",
            "expected_source": "POLICY-SALES-2026-01#1",
        },
        {
            "name": "approved_exception",
            "question": "2026年9月12日深圳国际展会已审批项目的住宿报销标准是多少？",
            "as_of": date(2026, 9, 12),
            "expected_outcome": "answered",
            "expected_source": "APPROVAL-EXPO-SZ-2026#7",
        },
        {
            "name": "unsupported_future_claim",
            "question": "2026年10月北区培训津贴是否已提高到900元？",
            "as_of": date(2026, 10, 2),
            "expected_outcome": "abstained",
            "expected_source": None,
        },
    ]
