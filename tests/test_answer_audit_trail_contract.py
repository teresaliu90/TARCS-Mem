from datetime import UTC, date, datetime

from tarcsmem.audit_trail import (
    AnswerAuditTrail,
    AnswerAuditTrailReader,
    AnswerEvidenceLineage,
    PolicyVersionRef,
)
from tarcsmem.models import AccessContext, MemoryRecord, SourceType
from tarcsmem.service import TARCSMemoryService


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


def test_service_persists_and_rebuilds_answer_evidence_lineage():
    service = TARCSMemoryService()
    service.seed()
    question = "2026年8月华南区销售折扣上限是多少？"

    result = service.query(question, date(2026, 8, 15))
    trail = service.get_answer_audit_trail(result.answer_id, AccessContext())

    assert result.answer_id.startswith("ans_")
    assert result.evidence_pack_id.startswith("pack_")
    assert result.correlation_id.startswith("corr_")
    assert trail is not None
    assert trail.answer_id == result.answer_id
    assert trail.evidence_pack_id == result.evidence_pack_id
    assert trail.outcome == "answered"
    assert trail.selected_evidence[0].memory_id == "sales-v2"
    assert trail.selected_evidence[0].supersedes_memory_id == "sales-v1"
    assert trail.verification["citation_membership"] == "passed"
    assert trail.integrity == {
        "chain_verified": False,
        "mode": "sqlite_reference_store",
    }
    assert question not in str(service.audit_trail(result.answer_id))
    service.close()


def test_answer_audit_reader_rechecks_tenant_and_record_roles():
    service = TARCSMemoryService()
    service.ingest(
        MemoryRecord(
            id="finance-policy",
            fact="财务审批上限为100万元。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="FINANCE-POLICY#1",
            authority=1.0,
            conflict_key="finance-limit",
            evidence=["FINANCE-POLICY#1"],
            tenant_id="tenant-a",
            allowed_roles=["finance"],
        )
    )
    finance_access = AccessContext.from_values("tenant-a", ["finance"])
    result = service.query("财务审批上限是多少？", date(2026, 8, 15), finance_access)

    assert service.get_answer_audit_trail(result.answer_id, finance_access) is not None
    assert (
        service.get_answer_audit_trail(
            result.answer_id, AccessContext.from_values("tenant-a", ["employee"])
        )
        is None
    )
    assert (
        service.get_answer_audit_trail(
            result.answer_id, AccessContext.from_values("tenant-b", ["finance"])
        )
        is None
    )
    service.close()
