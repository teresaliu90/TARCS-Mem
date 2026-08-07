import pytest
from fastapi.testclient import TestClient

from tarcsmem.adapters import QdrantVectorStore
from tarcsmem.api import create_app
from tarcsmem.models import AccessContext, MemoryRecord, SourceType


def governed_memory(
    record_id: str,
    tenant_id: str,
    *,
    allowed_roles: list[str] | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        fact="合成制度：采购审批上限为五万元。",
        source_type=SourceType.OFFICIAL_POLICY,
        source_ref=f"SYNTHETIC-{tenant_id}#{record_id}",
        authority=1.0,
        conflict_key=f"purchase-limit:{record_id}",
        evidence=[f"SYNTHETIC-{tenant_id}#{record_id}"],
        tenant_id=tenant_id,
        allowed_roles=list(allowed_roles or []),
        classification="confidential" if allowed_roles else "internal",
    )


def test_memory_projection_history_and_overview_share_one_access_boundary(tmp_path):
    app = create_app(str(tmp_path / "isolation.db"), api_key="")
    service = app.state.tarcsmem_service
    service.ingest(governed_memory("alpha-public", "alpha"))
    service.ingest(governed_memory("alpha-audit", "alpha", allowed_roles=["auditor"]))
    service.ingest(governed_memory("beta-private", "beta", allowed_roles=["auditor"]))

    with TestClient(app) as client:
        anonymous_list = client.get("/v1/memories", params={"tenant_id": "alpha"})
        auditor_list = client.get(
            "/v1/memories",
            params=[("tenant_id", "alpha"), ("roles", "auditor")],
        )
        overview = client.get(
            "/v1/console/overview",
            params=[("tenant_id", "alpha"), ("roles", "auditor")],
        )
        unknown = client.get("/v1/memories/does-not-exist", params={"tenant_id": "alpha"})
        foreign = client.get("/v1/memories/beta-private", params={"tenant_id": "alpha"})
        role_denied = client.get("/v1/memories/alpha-audit", params={"tenant_id": "alpha"})
        allowed = client.get(
            "/v1/memories/alpha-audit",
            params=[("tenant_id", "alpha"), ("roles", "auditor")],
        )
        unknown_audit = client.get(
            "/v1/memories/does-not-exist/audit", params={"tenant_id": "alpha"}
        )
        foreign_audit = client.get(
            "/v1/memories/beta-private/audit",
            params=[("tenant_id", "alpha"), ("roles", "auditor")],
        )
        allowed_audit = client.get(
            "/v1/memories/alpha-audit/audit",
            params=[("tenant_id", "alpha"), ("roles", "auditor")],
        )

    assert [item["id"] for item in anonymous_list.json()["items"]] == ["alpha-public"]
    assert {item["id"] for item in auditor_list.json()["items"]} == {
        "alpha-public",
        "alpha-audit",
    }
    assert overview.json()["total_memories"] == 2
    assert unknown.status_code == foreign.status_code == role_denied.status_code == 404
    assert unknown.json() == foreign.json() == role_denied.json()
    assert allowed.status_code == 200
    assert allowed.json()["memory"]["source_ref"].startswith("SYNTHETIC-alpha")
    assert unknown_audit.status_code == foreign_audit.status_code == 404
    assert unknown_audit.json() == foreign_audit.json()
    assert allowed_audit.status_code == 200
    assert "beta" not in allowed_audit.text
    service.close()


def test_query_and_answer_audit_do_not_reveal_denied_ids_or_counts(tmp_path):
    app = create_app(str(tmp_path / "answer-isolation.db"), api_key="")
    service = app.state.tarcsmem_service
    service.ingest(governed_memory("alpha-visible", "alpha"))
    service.ingest(governed_memory("alpha-role-hidden", "alpha", allowed_roles=["finance"]))
    service.ingest(governed_memory("beta-hidden", "beta"))

    with TestClient(app) as client:
        response = client.post(
            "/v1/query",
            json={
                "question": "采购审批上限是多少？",
                "as_of": "2026-08-06",
                "tenant_id": "alpha",
                "roles": [],
            },
        )
        payload = response.json()
        audit = client.get(
            f"/v1/answers/{payload['answer_id']}/audit",
            params={"tenant_id": "alpha"},
        )
        foreign = client.get(
            f"/v1/answers/{payload['answer_id']}/audit",
            params=[("tenant_id", "beta"), ("roles", "auditor")],
        )

    assert response.status_code == audit.status_code == 200
    serialized = response.text + audit.text
    assert "beta-hidden" not in serialized
    assert "alpha-role-hidden" not in serialized
    assert "tenant_denied" not in serialized
    assert "role_denied" not in serialized
    assert foreign.status_code == 404
    assert audit.json()["policy_versions"]["governance"]["policy_id"]
    service.close()


def test_overlapping_client_ids_cannot_overwrite_another_tenant(tmp_path):
    app = create_app(str(tmp_path / "overlap.db"), api_key="")
    service = app.state.tarcsmem_service
    original = service.ingest(governed_memory("shared-id", "alpha"))

    with pytest.raises(ValueError, match="unavailable"):
        service.ingest(governed_memory("shared-id", "beta"))

    stored = service.store.get("shared-id")
    assert stored is not None
    assert stored.tenant_id == "alpha"
    assert stored.source_ref == original.source_ref
    service.close()


def test_remote_qdrant_query_pushes_tenant_filter_to_the_source(monkeypatch):
    store = QdrantVectorStore("http://qdrant.invalid", "test", dimension=2)
    captured: dict[str, object] = {}

    monkeypatch.setattr(store, "ensure_collection", lambda: None)

    def request(method, path, payload=None):
        captured.update({"method": method, "path": path, "payload": payload})
        return {"result": {"points": []}}

    monkeypatch.setattr(store, "_request", request)
    assert store.search([0.0, 1.0], limit=7, tenant_id="alpha") == []
    assert captured["method"] == "POST"
    assert captured["payload"]["filter"] == {
        "must": [{"key": "tenant_id", "match": {"value": "alpha"}}]
    }


def test_access_filter_remains_fail_closed_for_empty_roles():
    record = governed_memory("role-only", "alpha", allowed_roles=["finance"])
    access = AccessContext.from_values("alpha", [])
    from tarcsmem.retrieval import filter_accessible_records

    visible, denied = filter_accessible_records([record], access)
    assert visible == []
    assert denied == [{"id": "role-only", "reason": "access denied: role not allowed"}]
