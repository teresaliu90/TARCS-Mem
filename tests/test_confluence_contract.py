import json
import urllib.error
from pathlib import Path

import pytest

from tarcsmem.chunking import chunk_text
from tarcsmem.confluence import ConfluenceConnector
from tarcsmem.models import EventType, MemoryStatus, SourceType
from tarcsmem.service import TARCSMemoryService

FIXTURE_DIR = Path(__file__).parents[1] / "examples" / "confluence-contract" / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class CursorFixtureAPI:
    def __init__(self):
        self.requests: list[str] = []

    def __call__(self, request, **kwargs):
        self.requests.append(request.full_url)
        name = (
            "initial-page-2.json"
            if "cursor=synthetic-page-2" in request.full_url
            else "initial-page-1.json"
        )
        return FakeResponse(fixture(name))


class StaticFixtureAPI:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, request, **kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


def connector(api, **kwargs):
    return ConfluenceConnector(
        "https://example.atlassian.net",
        "connector@example.invalid",
        "synthetic-token",
        "42",
        opener=api,
        **kwargs,
    )


def one_page_payload(name: str = "initial-page-1.json") -> dict:
    payload = fixture(name)
    payload["_links"] = {}
    return payload


def test_published_fixtures_are_synthetic_and_secret_free():
    forbidden = ("atlassian.net", "authorization", "api_token", "secret", "@")
    for path in FIXTURE_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        assert all(value not in text for value in forbidden), path
        json.loads(text)


def test_cursor_duplicate_delivery_is_deduplicated_and_acl_mapping_is_preserved(tmp_path):
    api = CursorFixtureAPI()
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "contract.db")
    checkpoint = tmp_path / "checkpoint.json"

    first = source.sync(
        service,
        checkpoint,
        tenant_id="synthetic-tenant",
        classification="confidential",
        allowed_roles=["auditor", "policy-reader", "auditor"],
    )
    second = source.sync(
        service,
        checkpoint,
        tenant_id="synthetic-tenant",
        classification="confidential",
        allowed_roles=["auditor", "policy-reader"],
    )

    records = service.store.list_all()
    assert first.scanned_pages == 2 and first.ingested_records == 2
    assert second.changed_pages == 0 and second.ingested_records == 0
    assert len(records) == 2
    assert all(record.source_type is SourceType.MEETING_NOTE for record in records)
    assert all(record.status is MemoryStatus.PENDING for record in records)
    assert all(record.classification == "confidential" for record in records)
    assert all(record.allowed_roles == ["auditor", "policy-reader"] for record in records)
    assert (
        sum(
            event["event_type"] == EventType.INGESTED.value
            for record in records
            for event in service.store.audit_trail(record.id)
        )
        == 2
    )
    service.close()


def test_rate_limit_retry_converges_without_duplicate_memories(tmp_path):
    fixture_api = CursorFixtureAPI()
    delays: list[float] = []
    calls = 0

    def retrying_api(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "synthetic rate limit",
                {"Retry-After": "0"},
                None,
            )
        return fixture_api(request, **kwargs)

    source = connector(retrying_api, sleep=delays.append)
    service = TARCSMemoryService(tmp_path / "retry.db")
    checkpoint = tmp_path / "checkpoint.json"

    first = source.sync(service, checkpoint)
    second = source.sync(service, checkpoint)

    assert first.ingested_records == 2 and second.ingested_records == 0
    assert service.store.count() == 2
    assert delays == [0.0]
    service.close()


def test_content_hash_change_with_reused_version_creates_a_new_projection(tmp_path):
    api = StaticFixtureAPI(one_page_payload())
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "hash-change.db")
    checkpoint = tmp_path / "checkpoint.json"
    source.sync(service, checkpoint)
    first_id = service.store.list_all()[0].id

    api.payload = one_page_payload("same-version-content-change.json")
    report = source.sync(service, checkpoint)

    records = service.store.list_all()
    assert report.changed_pages == 1 and report.ingested_records == 1
    assert report.expired_records == 1
    assert len(records) == 2 and len({record.id for record in records}) == 2
    assert (
        next(record for record in records if record.id == first_id).status is MemoryStatus.EXPIRED
    )
    current = next(record for record in records if record.id != first_id)
    assert current.status is MemoryStatus.PENDING
    assert "90 units" in current.fact
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert saved["pages"]["91001"]["content_hash"] == current.metadata["content_hash"]
    service.close()


def test_unconfirmed_missing_page_remains_actionable_until_explicit_expiry(tmp_path):
    api = StaticFixtureAPI(one_page_payload())
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "missing.db")
    checkpoint = tmp_path / "checkpoint.json"
    source.sync(service, checkpoint)
    record = service.store.list_all()[0]
    service.review(record.id, "approve", "synthetic-reviewer")
    events_before = service.store.audit_trail(record.id)

    api.payload = fixture("no-visible-pages.json")
    unconfirmed = source.sync(service, checkpoint)
    retained = json.loads(checkpoint.read_text(encoding="utf-8"))

    assert unconfirmed.missing_page_ids == ("91001",)
    assert unconfirmed.expired_records == 0
    assert retained["pages"]["91001"]["missing"] is True
    assert service.store.get(record.id).status is MemoryStatus.VERIFIED_ACTIVE

    confirmed = source.sync(service, checkpoint, expire_missing=True)
    events_after = service.store.audit_trail(record.id)

    assert confirmed.missing_page_ids == ("91001",)
    assert confirmed.expired_records == 1
    assert service.store.get(record.id).status is MemoryStatus.EXPIRED
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["pages"] == {}
    assert events_after[: len(events_before)] == events_before
    assert events_after[-1]["event_type"] == EventType.STATUS_CHANGED.value
    assert events_after[-1]["detail"]["reason"] == (
        "Confluence missing page was explicitly confirmed"
    )
    service.close()


def test_api_page_failure_does_not_create_a_partial_sync(tmp_path):
    first = fixture("initial-page-1.json")
    calls = 0

    def failing_api(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(first)
        raise urllib.error.HTTPError(request.full_url, 503, "synthetic outage", {}, None)

    source = connector(failing_api, max_retries=0)
    service = TARCSMemoryService(tmp_path / "api-partial.db")
    checkpoint = tmp_path / "checkpoint.json"

    with pytest.raises(RuntimeError, match="HTTP 503"):
        source.sync(service, checkpoint)

    assert service.store.count() == 0
    assert not checkpoint.exists()
    service.close()


def test_ingest_failure_retry_fills_missing_chunks_without_duplicate_events(tmp_path):
    body = " ".join(f"synthetic clause {index}." for index in range(240))
    payload = one_page_payload()
    payload["results"][0]["body"]["storage"]["value"] = f"<p>{body}</p>"
    api = StaticFixtureAPI(payload)
    source = connector(api)
    service = TARCSMemoryService(tmp_path / "ingest-partial.db")
    checkpoint = tmp_path / "checkpoint.json"

    class FailSecondIngest:
        memory = service

        def __init__(self):
            self.calls = 0

        def ingest_record(self, record):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("synthetic ingest failure")
            return service.ingest(record)

    target = FailSecondIngest()
    with pytest.raises(RuntimeError, match="synthetic ingest failure"):
        source.sync(target, checkpoint)

    assert service.store.count() == 1
    assert not checkpoint.exists()

    report = source.sync(service, checkpoint)
    expected_chunks = len(chunk_text(f"Synthetic Travel Policy\n{body}"))
    records = service.store.list_all()

    assert report.ingested_records == expected_chunks - 1
    assert len(records) == expected_chunks
    assert len({record.id for record in records}) == expected_chunks
    assert all(
        sum(
            event["event_type"] == EventType.INGESTED.value
            for event in service.store.audit_trail(record.id)
        )
        == 1
        for record in records
    )
    service.close()


def test_repeated_pagination_cursor_fails_closed():
    payload = fixture("initial-page-1.json")
    payload["_links"]["next"] = "/wiki/api/v2/spaces/42/pages?cursor=repeated"
    api = StaticFixtureAPI(payload)

    with pytest.raises(RuntimeError, match="repeated cursor"):
        connector(api).list_pages()
