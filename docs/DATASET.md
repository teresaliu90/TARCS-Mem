# Dataset protocol

The included data is fully synthetic and deterministic. It represents fictional sales and travel policies. It intentionally includes:

- a newer official policy that supersedes an old policy;
- an unapproved meeting-note contradiction;
- an approved temporary exception;
- a future claim that should not become active evidence.

This makes expected answer, business valid-time and citation deterministic. The generator never uses customer files, employer rules, chat logs, credentials or production databases.

## Data sources for the portfolio version

| Layer | Source | What it validates | Commit raw data? |
| --- | --- | --- | --- |
| Core governance | This repository's deterministic fictional policy/event scenarios | time validity, source authority, version conflict, write pollution and abstention | Yes: only the small synthetic fixture and generator |
| Long-term memory | [LongMemEval](https://github.com/xiaowu0162/longmemeval) | cross-session recall, temporal reasoning and knowledge update | No: download locally and follow its terms |
| Financial document/table reasoning | [FinQA](https://finqasite.github.io/) | evidence-grounded numerical reasoning over reports and tables | No: download locally and follow its terms |
| Text-to-SQL, optional route | [BIRD Mini-Dev](https://github.com/bird-bench/mini_dev) | safe routing from a question to a structured-data/SQL workflow | No: download locally and follow its terms |
| Rule-drift SQL, optional V2 | [LiveSQLBench](https://livesqlbench.ai/) | changing business knowledge combined with database questions | No: download locally and follow its terms |
| Public finance retrieval, runnable in the UI | [BEIR FiQA](https://huggingface.co/datasets/BeIR/fiqa) | zero-shot / hybrid retrieval and reranking over a financial corpus | No: click **下载并接入 FiQA**; the raw corpus stays in `data/external/` |

LongMemEval does **not** prove enterprise-policy governance; FinQA does **not** prove memory quality; BIRD does **not** prove RAG quality. Report every benchmark as a separate result, then use the synthetic governed scenarios to demonstrate TARCS-Mem's specific contribution.

Put external datasets under `data/external/`, which is gitignored. Keep only download instructions, preprocessing code, dataset version/hash and aggregate metrics in a public repository. Check each dataset's current licence and terms before redistribution or commercial use.

## FiQA in this repository

The **知识与数据集** tab calls Hugging Face's public dataset API only after an explicit click, then caches and imports a bounded FiQA sample (25–500 documents in the UI). This makes the local Agent demonstrable with a real public retrieval corpus without committing the full raw corpus. FiQA records are labelled `public_dataset` with authority `0.55`; they are traceable evidence for a public benchmark, not a substitute for an enterprise's approved policy source. The upstream dataset card lists a CC BY-SA 4.0 licence: verify current upstream terms before redistribution or commercial use.

The CLI evaluation additionally loads real FiQA test queries and qrels from the public dataset server, fetches the relevant corpus documents, and combines them with a bounded distractor sample. Only the aggregate [evaluation report](EVALUATION.md) is committed.

## Add a credible project benchmark

1. Generate at least 100 scenarios with a fixed random seed and save source documents, event stream and answer keys.
2. Split by conflict template, not merely by question, to prevent template leakage.
3. Manually review a held-out subset and report disagreement.
4. Add public long-memory benchmarks separately; do not relabel them as enterprise-policy results.
5. Publish prompts, model/version, configuration, raw outputs and evaluator code with each experiment.

## Suggested scenario fields

`scenario_id`, `question`, `as_of`, `documents`, `event_order`, `expected_outcome`, `expected_citations`, `expected_status`, `risk_type`.
