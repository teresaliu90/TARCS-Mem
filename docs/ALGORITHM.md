# TARCS-Mem algorithm

## Problem

For a query `q` at business time `t`, select evidence records that are relevant but also active, valid, authoritative, traceable, and affordable under a token budget. For writes, prevent weak or unverified assertions from becoming active facts.

## GuardWrite

Each candidate is assigned to a state:

```text
candidate -> pending -> verified_active -> superseded / expired
                    \-> rejected
```

Automatic activation is intentionally narrow: a traceable `official_policy`, `approved_exception`, or trusted `system_record` must pass source-specific confidence and durability thresholds. Meeting notes and user claims remain pending. Model inferences can never become fact memory without external evidence.

When records share a `conflict_key` and their valid-time windows overlap, the resolver automatically supersedes only when the incoming record is more authoritative, or is a newer official policy of equal authority. Ambiguous ties remain pending for review.

## GuardRead / TARCS

Hard eligibility is applied first:

\[
E(m,t) = [status(m)=active \lor (status(m)=superseded \land t\ is\ historical)] \land [valid\_from(m) \leq t \leq valid\_to(m)]
\]

Eligible evidence with non-zero query overlap is ranked after RRF fusion. A calibrated relevance floor is applied before token budgeting so unrelated high-authority records cannot consume the evidence budget:

\[
S(m,q)=0.45R(m,q)+0.15V(m,t)+0.20A(m)+0.15P(m)-0.05C(m)
\]

where `R` combines lexical/semantic/RRF relevance; `V` is temporal validity after hard filtering; `A` is source authority; `P` is provenance/reliability derived from source traceability, extraction confidence and durability; `C` is normalized estimated token cost.

The selector greedily recomputes and maximizes a Maximal Marginal Relevance objective under a token budget and retains at most one active record per conflict key. Pairwise diversity uses document tokens only; shared query tokens are not injected into every candidate:

\[
MMR(m)= (1-\lambda)S(m,q)-\lambda\max_{s\in Selected} Jaccard(tokens(m),tokens(s))
\]

This is an explicit, inspectable engineering algorithm rather than a claim of a new foundation-model architecture. The proposed research extension is to learn the ranker weights from adjudicated evidence labels and compare it with the fixed-weight version.

## Evaluation claims

Use only observed experiment results. Required ablations:

1. naive retrieval;
2. hybrid/RRF retrieval;
3. remove temporal hard filters;
4. remove authority/provenance terms;
5. remove GuardWrite;
6. remove budgeted MMR selection.

Operational retrieval tests also cover candidate oversampling before ACL/status/time filtering. This prevents a vector top-k dominated by inaccessible or stale records from causing a false abstention when an eligible result exists just below that preliminary cut.

Metrics: answer exactness, fresh-source selection, authoritative citation rate, conflict resolution accuracy, memory pollution rate, correct abstention, context tokens and P95 latency.
