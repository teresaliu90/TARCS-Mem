import json
import urllib.error

import pytest

from tarcsmem.confluence import ConfluenceConnector, ConfluencePage, confluence_storage_to_text
from tarcsmem.models import MemoryStatus
from tarcsmem.service import TARCSMemoryService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class PageAPI:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def __call__(self, request, **kwargs):
        self.requests.append(request)
        return FakeResponse({"results": self.pages, "_links": {}})


def page(page_id="101", version=1, body="<p>差旅上限为 500 元。</p>"):
    return {
        "id": page_id,
        "title": "差旅制度",
        "version": {"number": version, "createdAt": f"2026-08-0{version}T08:00:00Z"},
        "body": {"storage": {"value": body}},
        "_links": {"webui": f"/wiki/spaces/OPS/pages/{page_id}"},
    }


def connector(api):
    return ConfluenceConnector(
        "https://example.atlassian.net",
        "owner@example.com",
        "test-token",
        "42",
        opener=api,
    )


def test_storage_format_is_converted_to_clean_text():
    text = confluence_storage_to_text(
        "<h1>制度</h1><p>上限为 <strong>500</strong> 元。</p><script>secret()</script>"
    )
    assert text == "制度\n上限为 500 元。"


def test_incremental_sync_ingests_only_changed_page_versions(tmp_path):
    api = PageAPI([page()])
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "confluence.db")
    checkpoint = tmp_path / "checkpoint.json"

    first = source.sync(service, checkpoint)
    second = source.sync(service, checkpoint)
    api.pages = [page(version=2, body="<p>差旅上限调整为 600 元。</p>")]
    third = source.sync(service, checkpoint)

    assert first.changed_pages == 1 and first.ingested_records == 1
    assert second.changed_pages == 0 and second.ingested_records == 0
    assert third.changed_pages == 1 and third.ingested_records == 1
    records = service.store.list_all()
    assert len(records) == 2
    assert {record.status for record in records} == {
        MemoryStatus.PENDING,
        MemoryStatus.EXPIRED,
    }
    saved = json.loads(checkpoint.read_text())
    assert saved["schema_version"] == 2
    assert saved["tenant_id"] == "default"
    assert saved["pages"]["101"]["version"] == 2
    assert "test-token" not in checkpoint.read_text()
    assert api.requests[0].get_header("Authorization").startswith("Basic ")
    service.close()


def test_checkpoint_is_bound_to_one_tenant_and_cannot_be_reused(tmp_path):
    source = connector(PageAPI([page()]))
    service = TARCSMemoryService(tmp_path / "tenant-checkpoint.db")
    checkpoint = tmp_path / "checkpoint.json"
    source.sync(service, checkpoint, tenant_id="alpha")

    with pytest.raises(ValueError, match="different tenant"):
        source.sync(service, checkpoint, tenant_id="beta")

    assert {record.tenant_id for record in service.store.list_all()} == {"alpha"}
    service.close()


def test_deterministic_connector_ids_include_tenant_scope(tmp_path):
    source = connector(PageAPI([page()]))
    service = TARCSMemoryService(tmp_path / "tenant-ids.db")
    source.sync(service, tmp_path / "alpha.json", tenant_id="alpha")
    source.sync(service, tmp_path / "beta.json", tenant_id="beta")

    records = service.store.list_all()
    assert len(records) == 2
    assert len({record.id for record in records}) == 2
    assert {record.tenant_id for record in records} == {"alpha", "beta"}
    service.close()


def test_version_expiry_never_changes_another_tenants_matching_page(tmp_path):
    api = PageAPI([page()])
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "tenant-expiry.db")
    source.sync(service, tmp_path / "alpha.json", tenant_id="alpha")
    source.sync(service, tmp_path / "beta.json", tenant_id="beta")
    api.pages = [page(version=2, body="<p>差旅上限调整为 600 元。</p>")]

    report = source.sync(service, tmp_path / "beta.json", tenant_id="beta")

    by_tenant = {
        tenant: [record for record in service.store.list_all() if record.tenant_id == tenant]
        for tenant in ("alpha", "beta")
    }
    assert report.expired_records == 1
    assert [record.status for record in by_tenant["alpha"]] == [MemoryStatus.PENDING]
    assert {record.status for record in by_tenant["beta"]} == {
        MemoryStatus.PENDING,
        MemoryStatus.EXPIRED,
    }
    service.close()


def test_missing_pages_are_reported_but_not_expired_without_opt_in(tmp_path):
    api = PageAPI([page()])
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "missing.db")
    checkpoint = tmp_path / "checkpoint.json"
    source.sync(service, checkpoint)
    api.pages = []

    report = source.sync(service, checkpoint)

    assert report.missing_page_ids == ("101",)
    assert report.expired_records == 0
    assert service.store.list_all()[0].status is MemoryStatus.PENDING
    service.close()


def test_missing_pages_can_be_expired_with_explicit_opt_in(tmp_path):
    api = PageAPI([page()])
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "missing-expire.db")
    checkpoint = tmp_path / "checkpoint.json"
    source.sync(service, checkpoint)
    api.pages = []

    report = source.sync(service, checkpoint, expire_missing=True)

    assert report.expired_records == 1
    assert service.store.list_all()[0].status is MemoryStatus.EXPIRED
    service.close()


def test_relative_cursor_pagination_fetches_each_page_once():
    payloads = iter(
        [
            {
                "results": [page("101")],
                "_links": {"next": "/wiki/api/v2/spaces/42/pages?cursor=next"},
            },
            {"results": [page("102")], "_links": {}},
        ]
    )
    requests = []

    def opener(request, **kwargs):
        requests.append(request.full_url)
        return FakeResponse(next(payloads))

    source = ConfluenceConnector(
        "https://example.atlassian.net",
        "owner@example.com",
        "test-token",
        "42",
        opener=opener,
    )

    assert [item.page_id for item in source.list_pages()] == ["101", "102"]
    assert requests[-1].endswith("cursor=next")


def test_external_page_link_falls_back_to_configured_site():
    source = connector(PageAPI([]))
    record = source._page_reference(
        ConfluencePage(
            "101",
            "Title",
            1,
            "2026-08-01T00:00:00Z",
            "Body",
            "https://attacker.example/x",
        )
    )
    assert record == "https://example.atlassian.net/wiki/spaces/42/pages/101"


def test_cross_origin_pagination_is_blocked():
    api = PageAPI([])
    source = connector(api)
    with pytest.raises(RuntimeError, match="leave the configured site"):
        source._request_json("https://attacker.example/steal")


def test_rate_limit_is_retried_without_exposing_credentials():
    calls = 0
    delays = []

    def opener(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": "0"},
                None,
            )
        return FakeResponse({"results": [page()], "_links": {}})

    source = ConfluenceConnector(
        "https://example.atlassian.net",
        "owner@example.com",
        "test-token",
        "42",
        opener=opener,
        sleep=delays.append,
    )

    assert [item.page_id for item in source.list_pages()] == ["101"]
    assert calls == 2
    assert delays == [0.0]
