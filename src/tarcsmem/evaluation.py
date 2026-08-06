from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .dataset import evaluation_cases
from .retrieval import naive_retrieve
from .service import TARCSMemoryService


def run_evaluation(db_path: str | Path) -> dict[str, object]:
    service = TARCSMemoryService(db_path)
    if service.store.count() == 0:
        service.seed()
    results: list[dict[str, object]] = []
    metric = defaultdict(float)
    cases = evaluation_cases()
    all_records = service.store.list_all()
    for case in cases:
        result = service.query(str(case["question"]), case["as_of"])
        expected_outcome = case["expected_outcome"]
        expected_source = case["expected_source"]
        baseline = naive_retrieve(str(case["question"]), all_records)[0]
        tarcs_source = result.citations[0] if result.citations else None
        correct = result.outcome == expected_outcome and tarcs_source == expected_source
        baseline_correct = baseline.source_ref == expected_source
        metric["tarcs_correct"] += float(correct)
        metric["baseline_correct"] += float(baseline_correct)
        metric["correct_abstention"] += float(
            expected_outcome == "abstained" and result.outcome == "abstained"
        )
        metric["selected_records"] += len(result.selected)
        metric["selected_tokens"] += sum(item.token_cost for item in result.selected)
        results.append(
            {
                "case": case["name"],
                "expected_source": expected_source,
                "tarcs_source": tarcs_source,
                "baseline_source": baseline.source_ref,
                "outcome": result.outcome,
                "correct": bool(correct),
            }
        )
    total = len(cases)
    summary = {
        "cases": total,
        "tarcs_accuracy": round(metric["tarcs_correct"] / total, 3),
        "naive_baseline_accuracy": round(metric["baseline_correct"] / total, 3),
        "correct_abstention_rate": round(metric["correct_abstention"] / total, 3),
        "avg_selected_records": round(metric["selected_records"] / total, 2),
        "avg_estimated_context_tokens": round(metric["selected_tokens"] / total, 2),
        "results": results,
    }
    service.close()
    return summary
