"""Incremental Confluence Cloud REST API v2 connector."""

from __future__ import annotations

import base64
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .chunking import chunk_text
from .models import AuditEvent, EventType, MemoryRecord, MemoryStatus, SourceType


class _StorageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def confluence_storage_to_text(value: str) -> str:
    parser = _StorageTextParser()
    parser.feed(value)
    parser.close()
    return parser.text()


@dataclass(frozen=True, slots=True)
class ConfluencePage:
    page_id: str
    title: str
    version: int
    updated_at: str
    body: str
    web_path: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.body}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ConfluenceSyncReport:
    scanned_pages: int
    changed_pages: int
    ingested_records: int
    unchanged_pages: int
    missing_page_ids: tuple[str, ...]
    expired_records: int
    checkpoint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "scanned_pages": self.scanned_pages,
            "changed_pages": self.changed_pages,
            "ingested_records": self.ingested_records,
            "unchanged_pages": self.unchanged_pages,
            "missing_page_ids": list(self.missing_page_ids),
            "expired_records": self.expired_records,
            "checkpoint": self.checkpoint,
        }


@dataclass(slots=True)
class ConfluenceConnector:
    base_url: str
    email: str
    api_token: str = field(repr=False)
    space_id: str
    timeout: int = 60
    max_retries: int = 3
    opener: Callable[..., Any] = field(default=urllib.request.urlopen, repr=False)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url.rstrip("/"))
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("Confluence base_url must be an HTTPS site origin")
        if not self.space_id.isdigit():
            raise ValueError("Confluence space_id must be numeric")
        if not self.email.strip() or not self.api_token:
            raise ValueError("Confluence email and API token are required")
        if not 1 <= self.timeout <= 300:
            raise ValueError("Confluence timeout must be between 1 and 300 seconds")
        if not 0 <= self.max_retries <= 8:
            raise ValueError("Confluence max_retries must be between 0 and 8")
        self.base_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @staticmethod
    def _tls_context():
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:  # pragma: no cover
            return ssl.create_default_context()

    def _safe_url(self, value: str) -> str:
        url = urllib.parse.urljoin(self.base_url + "/", value)
        parsed = urllib.parse.urlsplit(url)
        expected = urllib.parse.urlsplit(self.base_url)
        if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
            raise RuntimeError("Confluence pagination attempted to leave the configured site")
        if not parsed.path.startswith("/wiki/api/v2/"):
            raise RuntimeError("Confluence pagination returned an unexpected API path")
        return url

    def _request_json(self, url: str) -> dict[str, Any]:
        credentials = base64.b64encode(f"{self.email.strip()}:{self.api_token}".encode()).decode(
            "ascii"
        )
        request = urllib.request.Request(
            self._safe_url(url),
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {credentials}",
                "User-Agent": "TARCS-Mem/0.7 ConfluenceConnector",
            },
        )
        for attempt in range(self.max_retries + 1):
            try:
                with self.opener(
                    request, timeout=self.timeout, context=self._tls_context()
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt == self.max_retries:
                    raise RuntimeError(
                        f"Confluence API request failed with HTTP {exc.code}"
                    ) from exc
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                delay = float(retry_after) if retry_after.isdigit() else float(2**attempt)
                self.sleep(min(delay, 30.0))
            except urllib.error.URLError as exc:
                if attempt == self.max_retries:
                    raise RuntimeError("Confluence API request failed after retries") from exc
                self.sleep(min(float(2**attempt), 30.0))
        raise RuntimeError("Confluence API request failed")  # pragma: no cover

    def _page_reference(self, page: ConfluencePage) -> str:
        fallback = f"{self.base_url}/wiki/spaces/{self.space_id}/pages/{page.page_id}"
        if not page.web_path:
            return fallback
        candidate = urllib.parse.urljoin(self.base_url + "/", page.web_path)
        parsed = urllib.parse.urlsplit(candidate)
        expected = urllib.parse.urlsplit(self.base_url)
        if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
            return fallback
        return candidate

    def list_pages(self, limit: int = 100) -> list[ConfluencePage]:
        if not 1 <= limit <= 250:
            raise ValueError("Confluence page limit must be between 1 and 250")
        url = f"/wiki/api/v2/spaces/{self.space_id}/pages?" + urllib.parse.urlencode(
            {"limit": limit, "status": "current", "body-format": "storage"}
        )
        pages: dict[str, ConfluencePage] = {}
        visited_urls: set[str] = set()
        while url:
            safe_url = self._safe_url(url)
            if safe_url in visited_urls:
                raise RuntimeError("Confluence pagination returned a repeated cursor")
            visited_urls.add(safe_url)
            payload = self._request_json(url)
            for item in payload.get("results", []):
                storage = (item.get("body") or {}).get("storage") or {}
                body = confluence_storage_to_text(str(storage.get("value", "")))
                if not body:
                    continue
                version = item.get("version") or {}
                page = ConfluencePage(
                    page_id=str(item["id"]),
                    title=str(item.get("title", "Untitled")).strip(),
                    version=int(version.get("number", 1)),
                    updated_at=str(version.get("createdAt", item.get("createdAt", ""))),
                    body=body,
                    web_path=str((item.get("_links") or {}).get("webui", "")),
                )
                previous = pages.get(page.page_id)
                if previous is not None and previous != page:
                    raise RuntimeError(
                        "Confluence pagination returned conflicting payloads for one page"
                    )
                pages[page.page_id] = page
            url = str((payload.get("_links") or {}).get("next", ""))
        return list(pages.values())

    @staticmethod
    def _read_checkpoint(path: Path, tenant_id: str) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": 2, "tenant_id": tenant_id, "pages": {}}
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_version = payload.get("schema_version")
        if schema_version == 1:
            # v1 checkpoints predated tenant scoping and therefore belong only
            # to the historical default demo tenant.
            if tenant_id != "default":
                raise ValueError("legacy Confluence checkpoint is scoped to the default tenant")
            payload = {**payload, "schema_version": 2, "tenant_id": "default"}
        if schema_version not in {1, 2} or not isinstance(payload.get("pages"), dict):
            raise ValueError("unsupported Confluence checkpoint schema")
        if payload.get("tenant_id") != tenant_id:
            raise ValueError("Confluence checkpoint belongs to a different tenant")
        return payload

    @staticmethod
    def _target_service(target):
        return getattr(target, "memory", target)

    @staticmethod
    def _ingest(target, record: MemoryRecord) -> MemoryRecord:
        method = getattr(target, "ingest_record", None) or getattr(target, "ingest", None)
        if not callable(method):
            raise TypeError("sync target must expose ingest(record) or ingest_record(record)")
        return method(record)

    @staticmethod
    def _expire_records(
        service,
        page_ids: set[str],
        tenant_id: str,
        pending_only: bool,
        keep_version: int | None = None,
        keep_content_hash: str | None = None,
        reason: str = "Confluence incremental sync",
    ) -> int:
        expired = 0
        for record in service.store.list_all():
            if record.metadata.get("connector") != "confluence":
                continue
            if record.tenant_id != tenant_id:
                continue
            if str(record.metadata.get("page_id")) not in page_ids:
                continue
            if (
                keep_version is not None
                and int(record.metadata.get("page_version", 0)) == keep_version
                and (
                    keep_content_hash is None
                    or record.metadata.get("content_hash") == keep_content_hash
                )
            ):
                continue
            allowed = (
                {MemoryStatus.PENDING}
                if pending_only
                else {
                    MemoryStatus.PENDING,
                    MemoryStatus.VERIFIED_ACTIVE,
                }
            )
            if record.status not in allowed:
                continue
            record.status = MemoryStatus.EXPIRED
            service.store.save(record)
            service.store.append_event(
                AuditEvent(
                    EventType.STATUS_CHANGED,
                    record.id,
                    {"status": "expired", "reason": reason},
                )
            )
            expired += 1
        return expired

    def sync(
        self,
        target,
        checkpoint_path: str | Path,
        *,
        tenant_id: str = "default",
        classification: str = "internal",
        source_type: SourceType = SourceType.MEETING_NOTE,
        authority: float = 0.70,
        allowed_roles: list[str] | None = None,
        expire_missing: bool = False,
    ) -> ConfluenceSyncReport:
        """Fetch changed pages, ingest governed chunks and atomically checkpoint.

        Missing pages are reported but only expired when ``expire_missing`` is
        explicitly enabled because permission changes can look like deletion.
        """
        checkpoint_file = Path(checkpoint_path)
        tenant_id = tenant_id.strip()
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")
        checkpoint = self._read_checkpoint(checkpoint_file, tenant_id)
        if checkpoint.get("site") not in {None, self.base_url}:
            raise ValueError("Confluence checkpoint belongs to a different site")
        if checkpoint.get("space_id") not in {None, self.space_id}:
            raise ValueError("Confluence checkpoint belongs to a different space")
        old_pages: dict[str, dict[str, Any]] = checkpoint["pages"]
        pages = self.list_pages()
        current_ids = {page.page_id for page in pages}
        missing = tuple(sorted(set(old_pages) - current_ids))
        changed = [
            page
            for page in pages
            if old_pages.get(page.page_id, {}).get("version") != page.version
            or old_pages.get(page.page_id, {}).get("content_hash") != page.content_hash
        ]
        service = self._target_service(target)
        ingested = 0
        expired = 0
        for page in changed:
            for chunk_index, text in enumerate(chunk_text(f"{page.title}\n{page.body}"), 1):
                identity = (
                    f"{tenant_id}:{self.base_url}:{self.space_id}:"
                    f"{page.page_id}:{page.version}:{page.content_hash}:{chunk_index}"
                )
                record_id = str(uuid5(NAMESPACE_URL, identity))
                if service.store.get(record_id) is not None:
                    continue
                reference = self._page_reference(page)
                valid_from = date.fromisoformat(page.updated_at[:10]) if page.updated_at else None
                record = MemoryRecord(
                    id=record_id,
                    fact=text,
                    source_type=source_type,
                    source_ref=f"{reference}#v{page.version}-chunk-{chunk_index}",
                    authority=authority,
                    conflict_key=f"confluence:{self.space_id}:{page.page_id}:chunk:{chunk_index}",
                    valid_from=valid_from,
                    evidence=[reference],
                    tenant_id=tenant_id,
                    allowed_roles=list(allowed_roles or []),
                    classification=classification,
                    metadata={
                        "connector": "confluence",
                        "space_id": self.space_id,
                        "page_id": page.page_id,
                        "page_version": page.version,
                        "content_hash": page.content_hash,
                        "chunk": chunk_index,
                    },
                )
                self._ingest(target, record)
                ingested += 1
            # Expire the old projection even when every deterministic record
            # already exists. This is the expected recovery path when an
            # earlier run ingested all chunks but failed before checkpointing.
            expired += self._expire_records(
                service,
                {page.page_id},
                tenant_id,
                pending_only=True,
                keep_version=page.version,
                keep_content_hash=page.content_hash,
                reason="Confluence page version or content hash was replaced",
            )
        if expire_missing and missing:
            expired += self._expire_records(
                service,
                set(missing),
                tenant_id,
                pending_only=False,
                reason="Confluence missing page was explicitly confirmed",
            )
        next_pages = {
            page.page_id: {
                "version": page.version,
                "content_hash": page.content_hash,
                "updated_at": page.updated_at,
            }
            for page in pages
        }
        if not expire_missing:
            # A page can disappear because connector permissions changed. Keep
            # the last safe checkpoint entry until an operator explicitly
            # confirms expiry, so a later --expire-missing run can still act.
            for page_id in missing:
                next_pages[page_id] = {**old_pages[page_id], "missing": True}
        next_checkpoint = {
            "schema_version": 2,
            "tenant_id": tenant_id,
            "site": self.base_url,
            "space_id": self.space_id,
            "pages": next_pages,
        }
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint_file.with_suffix(checkpoint_file.suffix + ".part")
        temporary.write_text(
            json.dumps(next_checkpoint, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(checkpoint_file)
        return ConfluenceSyncReport(
            scanned_pages=len(pages),
            changed_pages=len(changed),
            ingested_records=ingested,
            unchanged_pages=len(pages) - len(changed),
            missing_page_ids=missing,
            expired_records=expired,
            checkpoint=str(checkpoint_file),
        )
