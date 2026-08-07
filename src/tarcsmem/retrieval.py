from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .models import AccessContext, MemoryRecord, MemoryStatus, RankedEvidence

ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
HAN_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def record_access_denial(record: MemoryRecord, access: AccessContext) -> str | None:
    """Return a privacy-safe denial reason, or ``None`` when access is allowed.

    This boundary deliberately ignores lifecycle status and business time so it
    can be shared by current-memory, history, review, and retrieval APIs.  The
    retrieval pipeline applies its stricter status/time rules afterwards.
    """

    if record.tenant_id != access.tenant_id:
        return "access denied: tenant boundary"
    if record.classification == "restricted" and not record.allowed_roles:
        return "access denied: restricted ACL missing"
    if record.allowed_roles and not (set(record.allowed_roles) & access.roles):
        return "access denied: role not allowed"
    return None


def filter_accessible_records(
    records: Iterable[MemoryRecord], access: AccessContext
) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
    """Apply tenant and document ACL checks without disclosing required roles."""

    accessible: list[MemoryRecord] = []
    denied: list[dict[str, str]] = []
    for record in records:
        reason = record_access_denial(record, access)
        if reason is None:
            accessible.append(record)
        else:
            denied.append({"id": record.id, "reason": reason})
    return accessible, denied


def tokens(text: str) -> list[str]:
    """Return ASCII terms and Chinese character bigrams.

    A character-only tokenizer makes unrelated Chinese policies appear relevant
    because generic characters such as “报” or “销” overlap. Bigrams are still
    dependency-free but make the reference retrieval substantially less noisy.
    """
    normalized = text.lower()
    result = ASCII_TOKEN_RE.findall(normalized)
    for run in HAN_RUN_RE.findall(normalized):
        if len(run) == 1:
            result.append(run)
        else:
            result.extend(run[index : index + 2] for index in range(len(run) - 1))
    return result


def lexical_score(query: str, text: str) -> float:
    q, d = set(tokens(query)), set(tokens(text))
    return len(q & d) / len(q) if q else 0.0


def semantic_score(query: str, text: str) -> float:
    """Dependency-free hashed bag-of-token cosine for reproducible local demos.

    Replace with BGE-M3/e5 embeddings through an adapter in real deployments.
    """
    q, d = Counter(tokens(query)), Counter(tokens(text))
    numerator = sum(q[token] * d[token] for token in q)
    denominator = math.sqrt(sum(v * v for v in q.values()) * sum(v * v for v in d.values()))
    return numerator / denominator if denominator else 0.0


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, record_id in enumerate(ranking, start=1):
            fused[record_id] = fused.get(record_id, 0.0) + 1 / (k + rank)
    peak = max(fused.values(), default=1.0)
    return {record_id: score / peak for record_id, score in fused.items()}


def token_cost(text: str) -> int:
    return max(1, len(tokens(text)))


def relevance_vector(record: MemoryRecord) -> set[str]:
    """Represent document content for diversity scoring.

    The query is intentionally excluded: adding the same query tokens to every
    candidate inflates pairwise overlap and makes distinct evidence look
    redundant.
    """
    return set(tokens(record.fact))


@dataclass(slots=True)
class TARCSConfig:
    relevance_weight: float = 0.45
    validity_weight: float = 0.15
    authority_weight: float = 0.20
    reliability_weight: float = 0.15
    cost_weight: float = 0.05
    diversity_lambda: float = 0.20
    max_context_tokens: int = 220
    top_n: int = 20
    min_relevance: float = 0.18


class TARCSRetriever:
    """GuardRead: hard constraints, RRF, TARCS scoring and token-budgeted selection."""

    def __init__(self, config: TARCSConfig | None = None) -> None:
        self.config = config or TARCSConfig()

    def _hard_filter(
        self,
        records: Iterable[MemoryRecord],
        as_of: date,
        access: AccessContext | None = None,
    ) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
        access = access or AccessContext()
        accessible, excluded = filter_accessible_records(records, access)
        eligible: list[MemoryRecord] = []
        for record in accessible:
            historical_version = (
                record.status is MemoryStatus.SUPERSEDED
                and record.valid_to is not None
                and record.is_valid_at(as_of)
            )
            if record.status is not MemoryStatus.VERIFIED_ACTIVE and not historical_version:
                excluded.append(
                    {"id": record.id, "reason": f"status={record.status.value} is not eligible"}
                )
            elif not record.is_valid_at(as_of):
                excluded.append({"id": record.id, "reason": "outside business valid-time window"})
            else:
                eligible.append(record)
        return eligible, excluded

    def filter_accessible(
        self,
        records: Iterable[MemoryRecord],
        access: AccessContext | None = None,
    ) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
        """Public tenant/ACL boundary for projection, history, and admin APIs."""

        return filter_accessible_records(records, access or AccessContext())

    def filter_records(
        self,
        records: Iterable[MemoryRecord],
        as_of: date,
        access: AccessContext | None = None,
    ) -> tuple[list[MemoryRecord], list[dict[str, str]]]:
        """Public hard-filter boundary shared by vector and core retrieval paths."""
        return self._hard_filter(records, as_of, access)

    @staticmethod
    def _reliability(record: MemoryRecord) -> float:
        provenance = 1.0 if record.evidence and record.source_ref else 0.0
        return 0.45 * record.extraction_confidence + 0.35 * provenance + 0.20 * record.durable_value

    def rank(
        self,
        query: str,
        records: Iterable[MemoryRecord],
        as_of: date,
        access: AccessContext | None = None,
    ) -> tuple[list[RankedEvidence], list[dict[str, str]]]:
        eligible, excluded = self._hard_filter(records, as_of, access)
        lexical_scores = {item.id: lexical_score(query, item.fact) for item in eligible}
        semantic_scores = {item.id: semantic_score(query, item.fact) for item in eligible}
        # Zero-score records must not gain relevance merely because RRF received
        # a total ordering containing every record.
        lexical = sorted(
            (item for item in eligible if lexical_scores[item.id] > 0),
            key=lambda item: lexical_scores[item.id],
            reverse=True,
        )
        semantic = sorted(
            (item for item in eligible if semantic_scores[item.id] > 0),
            key=lambda item: semantic_scores[item.id],
            reverse=True,
        )
        fused = reciprocal_rank_fusion(
            [[item.id for item in lexical], [item.id for item in semantic]]
        )
        ranked: list[RankedEvidence] = []
        for record in eligible:
            lex = lexical_scores[record.id]
            sem = semantic_scores[record.id]
            rrf = fused.get(record.id, 0.0)
            reliability = self._reliability(record)
            cost = token_cost(record.fact)
            normalized_cost = min(cost / self.config.max_context_tokens, 1.0)
            score = (
                self.config.relevance_weight * (0.55 * rrf + 0.45 * max(lex, sem))
                + self.config.validity_weight
                + self.config.authority_weight * record.authority
                + self.config.reliability_weight * reliability
                - self.config.cost_weight * normalized_cost
            )
            ranked.append(
                RankedEvidence(
                    record=record,
                    lexical_score=lex,
                    semantic_score=sem,
                    rrf_score=rrf,
                    tarcs_score=score,
                    token_cost=cost,
                    reasons=[
                        "historical version valid at requested business time"
                        if record.status is MemoryStatus.SUPERSEDED
                        else "valid at requested business time",
                        f"authority={record.authority:.2f}",
                        f"reliability={reliability:.2f}",
                    ],
                )
            )
        ranked.sort(key=lambda item: item.tarcs_score, reverse=True)
        return ranked[: self.config.top_n], excluded

    def relevant_candidates(
        self, candidates: list[RankedEvidence]
    ) -> tuple[list[RankedEvidence], list[dict[str, str]]]:
        """Apply the grounding floor before context budget and MMR selection."""
        relevant: list[RankedEvidence] = []
        excluded: list[dict[str, str]] = []
        for item in candidates:
            if max(item.lexical_score, item.semantic_score) >= self.config.min_relevance:
                relevant.append(item)
            else:
                excluded.append(
                    {"id": item.record.id, "reason": "relevance below configured grounding floor"}
                )
        return relevant, excluded

    def select(self, query: str, candidates: list[RankedEvidence]) -> list[RankedEvidence]:
        _ = query  # Kept in the public signature for adapter compatibility.
        selected: list[RankedEvidence] = []
        spent = 0
        selected_tokens: list[set[str]] = []
        seen_conflicts: set[str] = set()
        remaining = list(candidates)
        while remaining:
            best: tuple[float, RankedEvidence, set[str]] | None = None
            for candidate in remaining:
                if candidate.token_cost + spent > self.config.max_context_tokens:
                    continue
                if candidate.record.conflict_key in seen_conflicts:
                    continue
                candidate_tokens = relevance_vector(candidate.record)
                max_overlap = max(
                    (
                        len(candidate_tokens & prior) / max(1, len(candidate_tokens | prior))
                        for prior in selected_tokens
                    ),
                    default=0.0,
                )
                mmr = (
                    1 - self.config.diversity_lambda
                ) * candidate.tarcs_score - self.config.diversity_lambda * max_overlap
                if best is None or mmr > best[0]:
                    best = (mmr, candidate, candidate_tokens)
            if best is None or best[0] <= 0:
                break
            mmr, candidate, candidate_tokens = best
            candidate.reasons.append(f"selected by constrained MMR={mmr:.3f}")
            selected.append(candidate)
            spent += candidate.token_cost
            selected_tokens.append(candidate_tokens)
            seen_conflicts.add(candidate.record.conflict_key)
            remaining.remove(candidate)
        return selected


def naive_retrieve(
    query: str, records: Iterable[MemoryRecord], top_k: int = 1
) -> list[MemoryRecord]:
    """A deliberately weak baseline: lexical retrieval ignores status and validity."""
    return sorted(records, key=lambda item: lexical_score(query, item.fact), reverse=True)[:top_k]


def classify_route(query: str) -> str:
    lowered = query.lower()
    if any(token in lowered for token in ("销售额", "库存", "订单", "利润", "erp", "sql")):
        return "structured_data_or_hybrid"
    if any(token in lowered for token in ("比较", "分别", "同时", "以及")):
        return "multi_evidence_policy"
    if any(token in lowered for token in ("制度", "政策", "规则", "上限", "报销", "折扣", "生效")):
        return "temporal_policy"
    return "knowledge_rag"
