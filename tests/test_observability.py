from datetime import date

import pytest

from tarcsmem.observability import MetricsRegistry, TraceBuffer, Tracer
from tarcsmem.service import TARCSMemoryService


def test_nested_spans_share_trace_and_keep_parent_relation():
    tracer = Tracer()
    with tracer.span("parent") as parent, tracer.span("child") as child:
        pass
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id
    recent = tracer.buffer.recent(2)
    assert {item["name"] for item in recent} == {"parent", "child"}


def test_failed_span_records_only_exception_type():
    tracer = Tracer()
    with pytest.raises(RuntimeError, match="do not log this raw message"), tracer.span("failure"):
        raise RuntimeError("do not log this raw message")
    span = tracer.buffer.recent(1)[0]
    assert span["status"] == "error"
    assert span["error_type"] == "RuntimeError"
    assert "raw message" not in str(span)


def test_trace_buffer_is_bounded():
    tracer = Tracer(TraceBuffer(max_spans=2))
    for index in range(3):
        with tracer.span(f"span-{index}"):
            pass
    assert [item["name"] for item in tracer.buffer.recent(10)] == ["span-2", "span-1"]


def test_metrics_snapshot_and_prometheus_export():
    metrics = MetricsRegistry()
    metrics.increment("tarcsmem_queries_total", labels={"outcome": "answered"})
    for value in (10, 20, 30):
        metrics.observe("tarcsmem_query_duration_ms", value, {"route": "policy"})
    snapshot = metrics.snapshot()
    assert snapshot["counters"][0]["value"] == 1
    assert snapshot["observations"][0]["avg"] == 20
    assert snapshot["observations"][0]["p95"] == 30
    rendered = metrics.prometheus_text()
    assert 'tarcsmem_queries_total{outcome="answered"} 1.0' in rendered
    assert 'tarcsmem_query_duration_ms_p95{route="policy"} 30.0' in rendered


def test_service_query_exposes_trace_but_never_raw_question():
    service = TARCSMemoryService()
    service.seed()
    question = "2026年8月华南区销售折扣上限是多少？内部代号 blue-whale"
    result = service.query(question, date(2026, 8, 15))
    assert result.trace_id
    assert result.latency_ms is not None
    spans = service.observability.tracer.buffer.recent(50)
    root_span = next(span for span in spans if span["name"] == "tarcsmem.query")
    assert root_span["attributes"]["answer_id"] == result.answer_id
    assert root_span["attributes"]["evidence_pack_id"] == result.evidence_pack_id
    assert question not in str(spans)
    assert question not in str(service.audit_trail(result.answer_id))
    service.close()
