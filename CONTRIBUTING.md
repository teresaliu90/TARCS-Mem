# Contributing to TARCS-Mem

Thank you for improving trusted enterprise memory governance.

## Before opening a pull request

1. Do not include customer documents, credentials, PII, screenshots of internal systems or paid datasets.
2. Add or update tests for every behavior change, especially status, time, conflict, ACL, classification or abstention behavior.
3. Run `ruff check src tests` and `pytest -q` locally.
4. Explain the threat model and evaluation impact for security, retrieval or LLM changes.

## Design expectations

TARCS-Mem is policy-first: generation must not bypass admission, access controls, valid time, conflict resolution, evidence selection or the cloud-egress gate. Keep provider SDKs optional and preserve the dependency-light core.

For benchmarks, state the corpus, candidate construction, qrels, cutoffs, random seeds, hardware and limitations. Do not present a bounded candidate-pool result as a full-corpus leaderboard result.

## Issues and pull requests

Use the issue templates for reproducible bugs and proposals. Keep a pull request focused. Maintainers may ask for an adversarial test when a change affects data isolation, sensitive-content handling or evidence grounding.

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
