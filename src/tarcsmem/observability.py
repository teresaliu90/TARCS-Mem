"""Safe built-in metrics and tracing with no raw document or query capture."""

from __future__ import annotations

import math
import re
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import RLock
from time import perf_counter
from uuid import uuid4

_METRIC_NAME = re.compile(r"[^a-zA-Z0-9_:]")
_current_trace_id: ContextVar[str | None] = ContextVar("tarcsmem_trace_id", default=None)
_current_span_id: ContextVar[str | None] = ContextVar("tarcsmem_span_id", default=None)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in (labels or {}).items()))


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._observations: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = (
            defaultdict(list)
        )

    def increment(self, name: str, value: float = 1, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._counters[(name, _labels_key(labels))] += value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            bucket = self._observations[(name, _labels_key(labels))]
            bucket.append(float(value))
            if len(bucket) > 5_000:
                del bucket[:1_000]

    def snapshot(self) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            counters = [
                {"name": name, "labels": dict(labels), "value": value}
                for (name, labels), value in sorted(self._counters.items())
            ]
            observations = [
                {
                    "name": name,
                    "labels": dict(labels),
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 4),
                    "p95": round(_percentile(values, 0.95), 4),
                    "max": round(max(values), 4),
                }
                for (name, labels), values in sorted(self._observations.items())
                if values
            ]
        return {"counters": counters, "observations": observations}

    def prometheus_text(self) -> str:
        lines: list[str] = []
        snapshot = self.snapshot()
        for item in snapshot["counters"]:
            name = _METRIC_NAME.sub("_", str(item["name"]))
            labels = item["labels"]
            rendered = ""
            if labels:
                rendered = (
                    "{"
                    + ",".join(
                        f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
                        for key, value in sorted(labels.items())
                    )
                    + "}"
                )
            lines.append(f"{name}{rendered} {item['value']}")
        for item in snapshot["observations"]:
            base = _METRIC_NAME.sub("_", str(item["name"]))
            labels = item["labels"]
            rendered = ""
            if labels:
                rendered = (
                    "{"
                    + ",".join(
                        f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
                        for key, value in sorted(labels.items())
                    )
                    + "}"
                )
            lines.extend(
                [
                    f"{base}_count{rendered} {item['count']}",
                    f"{base}_avg{rendered} {item['avg']}",
                    f"{base}_p95{rendered} {item['p95']}",
                    f"{base}_max{rendered} {item['max']}",
                ]
            )
        return "\n".join(lines) + ("\n" if lines else "")


@dataclass(slots=True)
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    attributes: dict[str, str | int | float | bool]
    started_at_monotonic: float = field(default_factory=perf_counter)
    duration_ms: float = 0.0
    status: str = "ok"
    error_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
            "error_type": self.error_type,
            "attributes": dict(self.attributes),
        }


class TraceBuffer:
    def __init__(self, max_spans: int = 1_000) -> None:
        self._lock = RLock()
        self._spans: deque[SpanRecord] = deque(maxlen=max_spans)

    def append(self, span: SpanRecord) -> None:
        with self._lock:
            self._spans.append(span)

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        bounded = max(1, min(int(limit), 500))
        with self._lock:
            values = list(self._spans)[-bounded:]
        return [item.to_dict() for item in reversed(values)]


class Tracer:
    def __init__(self, buffer: TraceBuffer | None = None) -> None:
        self.buffer = buffer or TraceBuffer()

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, str | int | float | bool] | None = None,
    ) -> Iterator[SpanRecord]:
        parent_trace = _current_trace_id.get()
        parent_span = _current_span_id.get()
        trace_id = parent_trace or uuid4().hex
        record = SpanRecord(
            name=name,
            trace_id=trace_id,
            span_id=uuid4().hex[:16],
            parent_span_id=parent_span,
            attributes=dict(attributes or {}),
        )
        trace_token = _current_trace_id.set(trace_id)
        span_token = _current_span_id.set(record.span_id)
        try:
            yield record
        except Exception as exc:
            record.status = "error"
            record.error_type = type(exc).__name__
            raise
        finally:
            record.duration_ms = (perf_counter() - record.started_at_monotonic) * 1_000
            self.buffer.append(record)
            _current_span_id.reset(span_token)
            _current_trace_id.reset(trace_token)


class Observability:
    def __init__(self) -> None:
        self.metrics = MetricsRegistry()
        self.tracer = Tracer()
