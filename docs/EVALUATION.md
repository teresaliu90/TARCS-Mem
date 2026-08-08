# Evaluation protocol and current results

TARCS-Mem separates two claims that should not be mixed: governance correctness and public-corpus retrieval quality.

## Automated verification

The repository has 115 deterministic tests covering admission, temporal versioning, conflict handling, human review, abstention, tenant/role and connector-checkpoint isolation, the public synthetic Confluence connector contract, PII/credential controls, API authentication, DeepSeek provider switching and key-safe failures, governed prompt semantics, answer/record audit privacy, metrics, spans, public-evaluation code and the local Agent path.

Run:

```bash
pip install -e '.[dev,api]'
ruff check src tests
pytest -q
```

## Synthetic governance evaluation

`tarcsmem evaluate` uses four fictional, answer-keyed scenarios: current policy, historical policy, approved exception and unsupported claim. This validates system rules; it is not evidence of production retrieval performance.

## Real public FiQA evaluation

The checked-in report was generated from real FiQA test queries and relevance judgments (qrels). For laptop reproducibility, the candidate pool contains every fetched relevant document for the first 120 test queries plus 300 public corpus distractors.

| System | Recall@1 | Recall@5 | Recall@10 | MRR@10 | NDCG@10 | P95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical baseline | 0.1532 | 0.3075 | 0.3624 | 0.3748 | 0.2988 | 15.599 |
| Hashed semantic | 0.1298 | 0.2406 | 0.2799 | 0.3203 | 0.2474 | 19.666 |
| RRF lexical + semantic | 0.1447 | 0.3428 | 0.4058 | 0.4071 | 0.3273 | 35.417 |
| TARCS RRF + governance/cost | **0.2037** | **0.3711** | **0.4446** | **0.4839** | **0.3783** | 83.736 |

TARCS improves every reported retrieval metric over the lexical baseline in this expanded run, but its dependency-free implementation is roughly five times slower at P95. That trade-off is reported rather than hidden. The run covers 120 queries and 610 documents; its dataset SHA-256 is `562e7124d64632657e7529b866d308c8ed009fc260597deee20387f3704e8b8c`. Each metric includes a deterministic 95% bootstrap interval based on 1,000 resamples with seed 42; exact values are in the JSON report.

Reproduce it with:

```bash
tarcsmem evaluate-public --queries 120 --distractors 300 \
  --output docs/benchmarks/fiqa-public-report.json
```

Raw public data stays under gitignored `data/external/`. The committed [JSON report](benchmarks/fiqa-public-report.json) contains aggregate metrics, query IDs and hit flags, but no raw query text.

## Interpretation limits

- This is a bounded qrel-plus-distractor pool, not the full 57.6k-document FiQA corpus and not comparable with the official BEIR leaderboard.
- 120 queries are materially stronger than the earlier 20-query smoke run, but still not the full 648-query FiQA test split.
- The built-in hashed semantic scorer is reproducible and dependency-free; it is not the BGE model used by the optional local Agent.
- FiQA records share public/default governance attributes, so this ablation validates retrieval and cost terms. Temporal, authority, ACL and conflict behavior remain covered by deterministic governance tests rather than this public IR corpus.
- A production claim requires a frozen enterprise test set, domain-expert adjudication, confidence intervals, full-corpus retrieval, security/red-team cases and latency/load measurements.
