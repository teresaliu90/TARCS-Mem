from datetime import date

from tarcsmem.models import MemoryRecord, MemoryStatus, RankedEvidence, SourceType
from tarcsmem.retrieval import TARCSConfig, TARCSRetriever, reciprocal_rank_fusion, tokens


def item(record_id: str, fact: str, conflict_key: str | None = None) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        fact=fact,
        source_type=SourceType.OFFICIAL_POLICY,
        source_ref=f"POLICY#{record_id}",
        authority=0.9,
        conflict_key=conflict_key or record_id,
        evidence=[f"POLICY#{record_id}"],
        status=MemoryStatus.VERIFIED_ACTIVE,
    )


def test_chinese_tokenizer_uses_bigrams_not_single_character_noise():
    assert tokens("销售折扣 ABC_1") == ["abc_1", "销售", "售折", "折扣"]


def test_rrf_normalizes_peak_and_rewards_shared_results():
    scores = reciprocal_rank_fusion([["a", "b"], ["a", "c"]])
    assert scores["a"] == 1.0
    assert scores["b"] < scores["a"]


def test_selection_enforces_one_version_per_conflict_key():
    retriever = TARCSRetriever()
    ranked, _ = retriever.rank(
        "销售折扣",
        [item("v1", "销售折扣为百分之十", "sales"), item("v2", "销售折扣为百分之八", "sales")],
        date(2026, 8, 1),
    )
    selected = retriever.select("销售折扣", ranked)
    assert len(selected) == 1


def test_selection_respects_context_budget():
    retriever = TARCSRetriever(TARCSConfig(max_context_tokens=2))
    ranked, _ = retriever.rank(
        "sales discount", [item("long", "sales discount policy limit")], date(2026, 8, 1)
    )
    assert retriever.select("sales discount", ranked) == []


def test_zero_overlap_records_do_not_receive_rrf_relevance():
    retriever = TARCSRetriever()
    ranked, _ = retriever.rank(
        "销售折扣",
        [item("relevant", "销售折扣为百分之五"), item("unrelated", "员工食堂开放时间")],
        date(2026, 8, 1),
    )
    by_id = {candidate.record.id: candidate for candidate in ranked}
    assert by_id["relevant"].rrf_score == 1.0
    assert by_id["unrelated"].rrf_score == 0.0


def test_relevance_floor_runs_before_context_selection():
    retriever = TARCSRetriever(TARCSConfig(max_context_tokens=20, min_relevance=0.18))
    ranked, _ = retriever.rank(
        "销售折扣",
        [item("relevant", "销售折扣为百分之五"), item("unrelated", "员工食堂开放时间")],
        date(2026, 8, 1),
    )
    relevant, excluded = retriever.relevant_candidates(ranked)
    assert [candidate.record.id for candidate in relevant] == ["relevant"]
    assert excluded == [{"id": "unrelated", "reason": "relevance below configured grounding floor"}]


def test_greedy_mmr_prefers_diverse_evidence_within_budget():
    retriever = TARCSRetriever(TARCSConfig(max_context_tokens=2, diversity_lambda=0.2))

    def ranked(record_id: str, fact: str, score: float) -> RankedEvidence:
        return RankedEvidence(
            record=item(record_id, fact),
            lexical_score=1.0,
            semantic_score=1.0,
            rrf_score=1.0,
            tarcs_score=score,
            token_cost=1,
            reasons=[],
        )

    selected = retriever.select(
        "销售折扣",
        [
            ranked("a", "销售折扣上限", 1.0),
            ranked("b", "销售折扣上限规定", 0.99),
            ranked("c", "审批流程负责人", 0.95),
        ],
    )
    assert [candidate.record.id for candidate in selected] == ["a", "c"]
