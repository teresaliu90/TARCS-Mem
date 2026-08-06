from datetime import UTC, date, datetime

from tarcsmem.audit_trail import (
    AnswerAuditTrail,
    AnswerAuditTrailReader,
    AnswerEvidenceLineage,
    PolicyVersionRef,
)
from tarcsmem.models import AccessContext


def sample_trail() -> AnswerAuditTrail:
    return AnswerAuditTrail(
        answer_id="ans-001",
        evidence_pack_id="pack-001",
        correlation_id="corr-001",
        outcome="answered",
        created_at=datetime(2026, 8, 6, 10, 30, tzinfo=UTC),
        as_of=date(2026, 8, 1),
        query_hash="sha256:question",
        principal_snapshot_hash="sha256:principal",
        query_event_id="evt-query-001",
        evidence_pack_event_id="evt-pack-001",
        selected_evidence=(
            AnswerEvidenceLineage(
                memory_id="memory-001",
                source_ref="POLICY-2026#1",
                classification="internal",
                valid_from=date(2026, 1, 1),
                valid_to=None,
                selected_reason_codes=("ACTIVE_AT_AS_OF", "ROLE_ALLOWED"),
                scores={"rrf": 0.91, "tarcs": 0.88},
                write_event_ids=("evt-ingested-001", "evt-admitted-001"),
            ),
        ),
        excluded_summary={"acl_denied": 2},
        policy_versions={
            "governance": PolicyVersionRef(
                policy_id="enterprise-policy",
                version="2026-08-01",
                digest="sha256:policy",
            )
        },
        verification={"citation_membership": "passed"},
        integrity={"chain_verified": True},
        trace_id="trace-001",
    )


def test_answer_audit_trail_serializes_a_privacy_safe_contract():
    payload = sample_trail().to_dict()

    assert payload["answer_id"] == "ans-001"
    assert payload["created_at"] == "2026-08-06T10:30:00+00:00"
    assert payload["as_of"] == "2026-08-01"
    assert payload["selected_evidence"][0]["valid_from"] == "2026-01-01"
    assert payload["selected_evidence"][0]["selected_reason_codes"] == [
        "ACTIVE_AT_AS_OF",
        "ROLE_ALLOWED",
    ]
    assert payload["policy_versions"]["governance"]["digest"] == "sha256:policy"
    assert "question" not in payload
    assert "evidence_content" not in payload["selected_evidence"][0]


def test_answer_audit_reader_protocol_keeps_access_in_the_query_boundary():
    class FakeReader:
        def get_answer_audit_trail(
            self,
            answer_id: str,
            access: AccessContext,
            *,
            include_evidence_content: bool = False,
        ) -> AnswerAuditTrail | None:
            assert answer_id == "ans-001"
            assert access.tenant_id == "tenant-a"
            assert include_evidence_content is False
            return sample_trail()

    reader = FakeReader()
    assert isinstance(reader, AnswerAuditTrailReader)
    assert (
        reader.get_answer_audit_trail("ans-001", AccessContext.from_values("tenant-a", ["auditor"]))
        == sample_trail()
    )
