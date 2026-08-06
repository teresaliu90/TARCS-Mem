from datetime import date

import pytest

from tarcsmem.models import AccessContext, MemoryRecord, MemoryStatus, SourceType
from tarcsmem.retrieval import TARCSRetriever
from tarcsmem.service import TARCSMemoryService


def memory(
    record_id: str,
    tenant: str = "acme",
    roles: list[str] | None = None,
    classification: str = "internal",
) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        fact="华南区销售折扣上限为百分之十",
        source_type=SourceType.OFFICIAL_POLICY,
        source_ref=f"POLICY#{record_id}",
        authority=0.95,
        conflict_key=record_id,
        evidence=[f"POLICY#{record_id}"],
        status=MemoryStatus.VERIFIED_ACTIVE,
        tenant_id=tenant,
        allowed_roles=roles or [],
        classification=classification,
    )


def test_cross_tenant_record_is_filtered_before_ranking():
    ranked, excluded = TARCSRetriever().rank(
        "华南区折扣", [memory("foreign", tenant="other")], date(2026, 8, 1), AccessContext("acme")
    )
    assert ranked == []
    assert excluded == [{"id": "foreign", "reason": "access denied: tenant boundary"}]


def test_matching_role_can_retrieve_confidential_record():
    ranked, _ = TARCSRetriever().rank(
        "华南区折扣",
        [memory("confidential-record", roles=["finance"], classification="confidential")],
        date(2026, 8, 1),
        AccessContext.from_values("acme", ["finance"]),
    )
    assert [item.record.id for item in ranked] == ["confidential-record"]


def test_missing_role_is_denied_without_disclosing_required_role():
    _, excluded = TARCSRetriever().rank(
        "华南区折扣",
        [memory("role-protected-record", roles=["finance"], classification="confidential")],
        date(2026, 8, 1),
        AccessContext.from_values("acme", ["sales"]),
    )
    assert excluded[0]["reason"] == "access denied: role not allowed"
    assert "finance" not in str(excluded)


def test_restricted_memory_requires_an_acl():
    _, excluded = TARCSRetriever().rank(
        "华南区折扣",
        [memory("restricted", classification="restricted")],
        date(2026, 8, 1),
        AccessContext("acme"),
    )
    assert excluded[0]["reason"] == "access denied: restricted ACL missing"


def test_access_context_normalizes_roles_and_rejects_empty_tenant():
    context = AccessContext.from_values(" acme ", [" finance ", "finance", ""])
    assert context.tenant_id == "acme"
    assert context.roles == frozenset({"finance"})
    with pytest.raises(ValueError, match="tenant_id"):
        AccessContext.from_values(" ")


def test_memory_rejects_unknown_classification():
    with pytest.raises(ValueError, match="classification"):
        memory("bad", classification="top-secret")


def test_same_conflict_key_cannot_supersede_another_tenant():
    service = TARCSMemoryService()
    first_input = memory("tenant-a", tenant="acme")
    second_input = memory("tenant-b", tenant="globex")
    first_input.conflict_key = second_input.conflict_key = "shared-policy"
    first = service.ingest(first_input)
    second = service.ingest(second_input)
    assert service.store.get(first.id).status is MemoryStatus.VERIFIED_ACTIVE
    assert service.store.get(second.id).status is MemoryStatus.VERIFIED_ACTIVE
    service.close()
