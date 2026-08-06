"""Bounded real-data retrieval evaluation using official BEIR/FiQA qrels."""

from __future__ import annotations

import hashlib
import json
import math
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from random import Random
from time import perf_counter

from .models import MemoryRecord, MemoryStatus, SourceType
from .public_data import FIQA_DATASET_CARD, FIQA_ROWS_URL, load_fiqa_documents
from .retrieval import (
    TARCSConfig,
    TARCSRetriever,
    lexical_score,
    reciprocal_rank_fusion,
    semantic_score,
)

FIQA_QRELS_CARD = "https://huggingface.co/datasets/BeIR/fiqa-qrels"
FIQA_EVAL_CARD = "https://huggingface.co/datasets/orgrctera/beir_fiqa"
FIQA_FILTER_URL = "https://datasets-server.huggingface.co/filter"


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    query_id: str
    query: str
    relevant_ids: frozenset[str]


def _tls_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()


def _get_json(url: str, timeout: int) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "TARCS-Mem/0.7 benchmark"})
    with urllib.request.urlopen(request, timeout=timeout, context=_tls_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def _row_value(row: dict) -> dict:
    value = row.get("row", row)
    return value if isinstance(value, dict) else {}


def _fetch_corpus_document(document_id: str, timeout: int) -> dict[str, str] | None:
    params = urllib.parse.urlencode(
        {
            "dataset": "BeIR/fiqa",
            "config": "corpus",
            "split": "corpus",
            "where": f"\"_id\"='{document_id}'",
            "offset": 0,
            "length": 1,
        }
    )
    payload = _get_json(f"{FIQA_FILTER_URL}?{params}", timeout)
    rows = payload.get("rows", [])
    if not rows:
        return None
    item = _row_value(rows[0])
    text = str(item.get("text", "")).strip()
    if not text:
        return None
    return {
        "id": str(item.get("_id", document_id)),
        "title": str(item.get("title", "")).strip(),
        "text": text,
    }


def download_fiqa_evaluation_pool(
    query_limit: int = 120,
    distractor_limit: int = 150,
    data_dir: str | Path = "./data/external",
    timeout: int = 90,
) -> Path:
    """Create a reproducible candidate pool from public queries, qrels and corpus text.

    This is deliberately a bounded candidate-pool evaluation suitable for a
    laptop and CI artifact. It must not be compared with official full-corpus
    BEIR leaderboard numbers.
    """
    if not 1 <= query_limit <= 648:
        raise ValueError("query_limit must be between 1 and 648")
    if not 20 <= distractor_limit <= 2_000:
        raise ValueError("distractor_limit must be between 20 and 2000")
    target = Path(data_dir) / "fiqa" / f"eval-test-{query_limit}-{distractor_limit}.json"
    if target.exists() and target.stat().st_size > 2_048:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        query_rows: list[dict] = []
        for offset in range(0, query_limit, 100):
            query_params = urllib.parse.urlencode(
                {
                    "dataset": "orgrctera/beir_fiqa",
                    "config": "default",
                    "split": "test",
                    "offset": offset,
                    "length": min(100, query_limit - offset),
                }
            )
            payload = _get_json(f"{FIQA_ROWS_URL}?{query_params}", timeout)
            query_rows.extend(payload.get("rows", []))
        cases: list[dict[str, object]] = []
        relevant_ids: set[str] = set()
        for row in query_rows:
            item = _row_value(row)
            expected = item.get("expected_output", "[]")
            judgments = json.loads(expected) if isinstance(expected, str) else expected
            ids = [str(value["id"]) for value in judgments if int(value.get("score", 0)) > 0]
            if not ids:
                continue
            query_id = str(
                item.get("metadata.query_id")
                or (item.get("metadata") or {}).get("query_id")
                or len(cases)
            )
            cases.append(
                {
                    "query_id": query_id,
                    "query": str(item.get("input", "")).strip(),
                    "relevant_ids": ids,
                }
            )
            relevant_ids.update(ids)

        documents: dict[str, dict[str, str]] = {}
        # Fetch qrel documents concurrently, then sort the output so the cache
        # fingerprint remains deterministic regardless of completion order.
        with ThreadPoolExecutor(max_workers=12) as executor:
            pending = {
                executor.submit(_fetch_corpus_document, document_id, timeout): document_id
                for document_id in sorted(relevant_ids)
            }
            for future in as_completed(pending):
                document = future.result()
                if document:
                    documents[document["id"]] = document
        complete_cases = [case for case in cases if set(case["relevant_ids"]) & set(documents)]
        if not complete_cases:
            raise RuntimeError("FiQA qrels loaded but relevant corpus documents were unavailable")

        for document in load_fiqa_documents(distractor_limit, data_dir):
            if document.document_id not in documents:
                documents[document.document_id] = {
                    "id": document.document_id,
                    "title": document.title,
                    "text": document.text,
                }
        rendered = {
            "dataset": "BEIR/FiQA",
            "split": "test",
            "scope": "bounded_candidate_pool",
            "queries": complete_cases,
            "documents": [documents[key] for key in sorted(documents)],
            "source": {
                "corpus": FIQA_DATASET_CARD,
                "qrels": FIQA_QRELS_CARD,
                "evaluation_rows": FIQA_EVAL_CARD,
                "license": "CC BY-SA 4.0; verify upstream terms before redistribution",
            },
        }
        temporary = target.with_suffix(".part")
        temporary.write_text(json.dumps(rendered, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return target
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError("unable to download the bounded FiQA evaluation pool") from exc


def _load_pool(path: str | Path) -> tuple[list[RetrievalCase], list[MemoryRecord], str]:
    dataset_path = Path(path)
    raw = dataset_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    cases = [
        RetrievalCase(
            query_id=str(item["query_id"]),
            query=str(item["query"]),
            relevant_ids=frozenset(str(value) for value in item["relevant_ids"]),
        )
        for item in payload["queries"]
    ]
    records = [
        MemoryRecord(
            id=str(item["id"]),
            fact=(f"{item.get('title', '')}\n{item['text']}").strip(),
            source_type=SourceType.PUBLIC_DATASET,
            source_ref=f"FiQA/{item['id']}",
            authority=0.55,
            conflict_key=f"fiqa:{item['id']}",
            evidence=[f"{FIQA_DATASET_CARD}#{item['id']}"],
            status=MemoryStatus.VERIFIED_ACTIVE,
            classification="public",
        )
        for item in payload["documents"]
    ]
    return cases, records, hashlib.sha256(raw).hexdigest()


def _metrics(
    rankings: list[list[str]], cases: list[RetrievalCase], k: int = 10
) -> dict[str, float]:
    recall_1 = recall_5 = recall_k = reciprocal = ndcg = 0.0
    for ranking, case in zip(rankings, cases, strict=True):
        relevant = case.relevant_ids
        recall_1 += len(set(ranking[:1]) & relevant) / len(relevant)
        recall_5 += len(set(ranking[:5]) & relevant) / len(relevant)
        recall_k += len(set(ranking[:k]) & relevant) / len(relevant)
        first_rank = next(
            (index for index, doc_id in enumerate(ranking[:k], 1) if doc_id in relevant), None
        )
        reciprocal += 1 / first_rank if first_rank else 0.0
        dcg = sum(
            1 / math.log2(index + 1)
            for index, doc_id in enumerate(ranking[:k], 1)
            if doc_id in relevant
        )
        ideal = sum(1 / math.log2(index + 1) for index in range(1, min(len(relevant), k) + 1))
        ndcg += dcg / ideal if ideal else 0.0
    total = max(1, len(cases))
    return {
        "recall_at_1": round(recall_1 / total, 4),
        "recall_at_5": round(recall_5 / total, 4),
        f"recall_at_{k}": round(recall_k / total, 4),
        f"mrr_at_{k}": round(reciprocal / total, 4),
        f"ndcg_at_{k}": round(ndcg / total, 4),
    }


def _bootstrap_confidence_intervals(
    rankings: list[list[str]],
    cases: list[RetrievalCase],
    k: int,
    iterations: int = 1_000,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    if not cases:
        return {}
    rng = Random(seed)
    samples: dict[str, list[float]] = {}
    for _ in range(iterations):
        indices = [rng.randrange(len(cases)) for _ in cases]
        metrics = _metrics(
            [rankings[index] for index in indices],
            [cases[index] for index in indices],
            k,
        )
        for name, value in metrics.items():
            samples.setdefault(name, []).append(value)
    result: dict[str, dict[str, float]] = {}
    for name, values in samples.items():
        ordered = sorted(values)
        lower = ordered[int(0.025 * (len(ordered) - 1))]
        upper = ordered[int(0.975 * (len(ordered) - 1))]
        result[name] = {"lower_95": round(lower, 4), "upper_95": round(upper, 4)}
    return result


def _timed_rankings(
    cases: list[RetrievalCase], ranker, top_k: int
) -> tuple[list[list[str]], dict[str, float]]:
    rankings: list[list[str]] = []
    durations: list[float] = []
    for case in cases:
        started = perf_counter()
        rankings.append(ranker(case)[:top_k])
        durations.append((perf_counter() - started) * 1_000)
    ordered = sorted(durations)
    p95_index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))
    return rankings, {
        "mean_ms": round(sum(durations) / max(1, len(durations)), 3),
        "p95_ms": round(ordered[p95_index], 3) if ordered else 0.0,
    }


def run_fiqa_public_evaluation(pool_path: str | Path, top_k: int = 10) -> dict[str, object]:
    cases, records, fingerprint = _load_pool(pool_path)
    retriever = TARCSRetriever(TARCSConfig(top_n=max(20, top_k)))

    def lexical(case: RetrievalCase) -> list[str]:
        return [
            item.id
            for item in sorted(
                records, key=lambda item: lexical_score(case.query, item.fact), reverse=True
            )
        ]

    def semantic(case: RetrievalCase) -> list[str]:
        return [
            item.id
            for item in sorted(
                records, key=lambda item: semantic_score(case.query, item.fact), reverse=True
            )
        ]

    def rrf(case: RetrievalCase) -> list[str]:
        lexical_ids = lexical(case)
        semantic_ids = semantic(case)
        fused = reciprocal_rank_fusion([lexical_ids, semantic_ids])
        return sorted(fused, key=fused.get, reverse=True)

    def tarcs(case: RetrievalCase) -> list[str]:
        ranked, _ = retriever.rank(case.query, records, date(2026, 1, 1))
        return [item.record.id for item in ranked]

    rankers = {
        "lexical_baseline": lexical,
        "hashed_semantic": semantic,
        "rrf_lexical_semantic": rrf,
        "tarcs_rrf_governance_cost": tarcs,
    }
    system_rankings: dict[str, list[list[str]]] = {}
    systems: dict[str, dict[str, object]] = {}
    for name, ranker in rankers.items():
        rankings, latency = _timed_rankings(cases, ranker, top_k)
        system_rankings[name] = rankings
        systems[name] = {
            "metrics": _metrics(rankings, cases, top_k),
            "confidence_intervals": _bootstrap_confidence_intervals(rankings, cases, top_k),
            "retrieval_latency": latency,
        }

    per_case: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        per_case.append(
            {
                "query_id": case.query_id,
                "relevant_count": len(case.relevant_ids),
                "hits": {
                    name: bool(set(rankings[index]) & case.relevant_ids)
                    for name, rankings in system_rankings.items()
                },
            }
        )
    return {
        "dataset": "BEIR/FiQA",
        "split": "test",
        "scope": "bounded_candidate_pool",
        "queries": len(cases),
        "documents": len(records),
        "dataset_sha256": fingerprint,
        "top_k": top_k,
        "bootstrap": {"iterations": 1_000, "seed": 42, "interval": 0.95},
        "systems": systems,
        "per_case": per_case,
        "limitations": [
            "Uses a bounded pool of qrel documents plus public distractors, not all 57.6k documents.",
            "Numbers are reproducible portfolio evidence and are not comparable to the BEIR leaderboard.",
            "The dependency-free semantic score is not a substitute for the optional BGE reranker path.",
            "Public FiQA records share governance attributes, so this ablation measures retrieval and cost terms; temporal and authority controls are evaluated separately by deterministic governance cases.",
        ],
        "source": {
            "corpus": FIQA_DATASET_CARD,
            "qrels": FIQA_QRELS_CARD,
            "license": "CC BY-SA 4.0; raw data is cached outside Git",
        },
    }
