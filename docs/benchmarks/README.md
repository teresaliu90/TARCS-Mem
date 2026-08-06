# Benchmark artifacts

`fiqa-public-report.json` is the current 120-query ablation report. `fiqa-public-report-20.json` preserves the earlier smoke run for transparent historical comparison. Both are safe to commit because they contain aggregate metrics, dataset/source metadata, query IDs and hit flags—not raw queries or documents.

The raw FiQA cache is intentionally excluded from Git. See [../EVALUATION.md](../EVALUATION.md) for the exact protocol and limitations.
