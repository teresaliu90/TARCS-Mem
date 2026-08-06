# Observability

TARCS-Mem includes dependency-free observability so the reference implementation can be inspected without requiring an external platform.

## What is implemented

- Counters for ingestion outcomes, query outcomes, review outcomes, security findings, cloud-egress allow/block decisions, generated-citation verification outcomes, idempotent-write replays and rate-limit blocks.
- Observations for query duration and selected-evidence count, including average, maximum and P95.
- Nested spans for GuardWrite, GuardRead ranking/selection and human review.
- A bounded in-memory span buffer; query results expose `trace_id` and `latency_ms`.
- `GET /metrics` in Prometheus text format and `GET /v1/observability` for a local JSON snapshot.

Raw questions, document text, matched credentials and exception messages are deliberately excluded. Attributes are limited to route, counts, classifications, outcomes and whether tenant scoping is active.

Cloud-egress metrics use `tarcsmem_cloud_egress_total` with provider, outcome and (for a block) classification labels. They deliberately omit the question, record text and record ID; investigate a block through the local audit event and a request/trace correlation layer in a production deployment.

`tarcsmem_generation_verification_total` records `passed`, `missing` or `unsupported` source-label verification without capturing model output. Alert when block rates rise: it can expose a prompt regression, model-provider change or an attempted source hallucination.

`tarcsmem_api_rate_limit_total` and `tarcsmem_api_idempotency_total` provide privacy-safe pilot signals. Rate limits are process-local by design, so production alerting must use the gateway's aggregated metrics as the source of truth.

## Local check

```bash
export TARCSMEM_API_KEY=change-me
tarcsmem serve --db ./data/tarcsmem.db
curl -H 'Authorization: Bearer change-me' http://127.0.0.1:8000/metrics
curl -H 'Authorization: Bearer change-me' http://127.0.0.1:8000/v1/observability
```

## Production extension

Keep the current privacy contract when adding OpenTelemetry/OTLP and Phoenix, Grafana or another backend. Use a request ID or trace ID for investigation, keep tenant IDs pseudonymized, set finite retention, restrict dashboard access, and never turn on payload capture to debug a production incident.

Recommended initial SLOs must be calibrated on real traffic: availability, P95 query latency, error rate, correct-abstention rate, retrieval Recall@k on a frozen canary set, security-block rate and ACL-denial anomalies.
