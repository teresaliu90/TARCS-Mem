from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from .models import AuditEvent, EventType, MemoryRecord, MemoryStatus


class SQLiteMemoryStore:
    """A portable reference store. Production deployments should use a managed DB."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Gradio dispatches callbacks from a worker pool. A single local Agent
        # intentionally shares one store, so protect the connection with an
        # RLock and explicitly permit that well-defined cross-thread access.
        self._lock = RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self.connection.executescript(
                """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                conflict_key TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_conflict ON memories(conflict_key);
            CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                at TEXT NOT NULL,
                detail TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_record ON audit_events(record_id, at);
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                request_fingerprint TEXT NOT NULL,
                response_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_idempotency_created ON idempotency_keys(created_at);
                """
            )
            self.connection.commit()

    def count(self) -> int:
        with self._lock:
            return int(self.connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def status_counts(self) -> dict[str, int]:
        """Return lightweight governance counters for APIs and the local UI."""
        with self._lock:
            rows = self.connection.execute(
                "SELECT status, COUNT(*) AS total FROM memories GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["total"]) for row in rows}

    def save(self, record: MemoryRecord) -> None:
        payload = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.connection.execute(
                """
            INSERT INTO memories(id, conflict_key, status, payload) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET conflict_key=excluded.conflict_key,
              status=excluded.status, payload=excluded.payload
                """,
                (record.id, record.conflict_key, record.status.value, payload),
            )
            self.connection.commit()

    def get(self, record_id: str) -> MemoryRecord | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT payload FROM memories WHERE id = ?", (record_id,)
            ).fetchone()
        return MemoryRecord.from_dict(json.loads(row["payload"])) if row else None

    def list_all(self) -> list[MemoryRecord]:
        with self._lock:
            rows = self.connection.execute("SELECT payload FROM memories ORDER BY id").fetchall()
        return [MemoryRecord.from_dict(json.loads(row["payload"])) for row in rows]

    def by_conflict_key(
        self, conflict_key: str, tenant_id: str | None = None
    ) -> list[MemoryRecord]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT payload FROM memories WHERE conflict_key = ?", (conflict_key,)
            ).fetchall()
        records = [MemoryRecord.from_dict(json.loads(row["payload"])) for row in rows]
        if tenant_id is not None:
            records = [record for record in records if record.tenant_id == tenant_id]
        return records

    def records_with_status(self, statuses: Iterable[MemoryStatus]) -> list[MemoryRecord]:
        values = tuple(status.value for status in statuses)
        placeholders = ",".join("?" for _ in values)
        with self._lock:
            rows = self.connection.execute(
                f"SELECT payload FROM memories WHERE status IN ({placeholders})", values
            ).fetchall()
        return [MemoryRecord.from_dict(json.loads(row["payload"])) for row in rows]

    def append_event(self, event: AuditEvent) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO audit_events(id, record_id, event_type, at, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.record_id,
                    event.event_type.value,
                    event.at.isoformat(),
                    json.dumps(event.detail, ensure_ascii=False, sort_keys=True),
                ),
            )
            self.connection.commit()

    def idempotency_begin(
        self, key: str, request_fingerprint: str, ttl_seconds: int
    ) -> tuple[str, dict[str, object] | None]:
        """Atomically reserve a key or return its completed response.

        The key holds no raw request body. A concurrent request with the same
        key is reported as in progress instead of performing a second write.
        """
        cutoff = datetime.fromtimestamp(
            datetime.now(UTC).timestamp() - ttl_seconds, tz=UTC
        ).isoformat()
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self.connection.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))
            # Finish TTL cleanup before any early replay/conflict return so the
            # connection does not retain a write transaction in a long-lived API process.
            self.connection.commit()
            row = self.connection.execute(
                "SELECT request_fingerprint, response_json FROM idempotency_keys WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO idempotency_keys(key, request_fingerprint, response_json, created_at) "
                    "VALUES (?, ?, NULL, ?)",
                    (key, request_fingerprint, now),
                )
                self.connection.commit()
                return "new", None
            if str(row["request_fingerprint"]) != request_fingerprint:
                return "conflict", None
            if row["response_json"] is None:
                return "in_progress", None
            return "replay", json.loads(str(row["response_json"]))

    def idempotency_complete(self, key: str, response: dict[str, object]) -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE idempotency_keys SET response_json = ? WHERE key = ?",
                (json.dumps(response, ensure_ascii=False, sort_keys=True), key),
            )
            self.connection.commit()

    def idempotency_abandon(self, key: str) -> None:
        """Release a failed reservation so a client can retry the operation."""
        with self._lock:
            self.connection.execute(
                "DELETE FROM idempotency_keys WHERE key = ? AND response_json IS NULL", (key,)
            )
            self.connection.commit()

    def is_ready(self) -> bool:
        """Run a content-free local-store readiness probe."""
        try:
            with self._lock:
                self.connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def audit_trail(self, record_id: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM audit_events WHERE record_id = ? ORDER BY at", (record_id,)
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": EventType(row["event_type"]).value,
                "at": row["at"],
                "detail": json.loads(row["detail"]),
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self.connection.close()
