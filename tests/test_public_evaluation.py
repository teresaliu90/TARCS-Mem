import json

import pytest

from tarcsmem.public_evaluation import download_fiqa_evaluation_pool, run_fiqa_public_evaluation


def fixture_pool(tmp_path):
    path = tmp_path / "fiqa-pool.json"
    path.write_text(
        json.dumps(
            {
                "queries": [
                    {"query_id": "q1", "query": "retirement account tax", "relevant_ids": ["d1"]},
                    {"query_id": "q2", "query": "credit card interest", "relevant_ids": ["d2"]},
                ],
                "documents": [
                    {"id": "d1", "title": "Retirement", "text": "retirement account tax rules"},
                    {"id": "d2", "title": "Cards", "text": "credit card interest rate"},
                    {"id": "d3", "title": "Noise", "text": "unrelated mortgage information"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_public_evaluation_has_reproducible_metrics_and_fingerprint(tmp_path):
    report = run_fiqa_public_evaluation(fixture_pool(tmp_path))
    assert report["dataset"] == "BEIR/FiQA"
    assert report["queries"] == 2
    assert report["documents"] == 3
    assert len(report["dataset_sha256"]) == 64
    assert report["systems"]["lexical_baseline"]["metrics"]["recall_at_1"] == 1.0
    assert report["systems"]["tarcs_rrf_governance_cost"]["metrics"]["mrr_at_10"] == 1.0
    assert report["bootstrap"] == {"iterations": 1000, "seed": 42, "interval": 0.95}
    assert set(report["systems"]) == {
        "lexical_baseline",
        "hashed_semantic",
        "rrf_lexical_semantic",
        "tarcs_rrf_governance_cost",
    }


def test_report_does_not_publish_raw_queries(tmp_path):
    report = run_fiqa_public_evaluation(fixture_pool(tmp_path))
    serialized = json.dumps(report)
    assert "retirement account tax" not in serialized
    assert report["per_case"][0]["query_id"] == "q1"


@pytest.mark.parametrize("queries", [0, 649])
def test_download_rejects_unbounded_query_counts_before_network(tmp_path, queries):
    with pytest.raises(ValueError, match="query_limit"):
        download_fiqa_evaluation_pool(queries, 20, tmp_path)


@pytest.mark.parametrize("distractors", [19, 2001])
def test_download_rejects_unbounded_distractor_counts_before_network(tmp_path, distractors):
    with pytest.raises(ValueError, match="distractor_limit"):
        download_fiqa_evaluation_pool(1, distractors, tmp_path)
