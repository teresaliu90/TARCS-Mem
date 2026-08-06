# Contributing to TARCS-Mem

Thank you for improving trusted enterprise memory governance.

The public repository is the Community Edition. It is meant to stay useful on its own; hosted
operations, private integrations and organization-specific support are future service surfaces,
not missing pieces that contributors are expected to recreate in the core. Read the [community
and enterprise direction](docs/COMMUNITY_AND_ENTERPRISE.md) before proposing a commercial-facing
feature.

You do not need to understand the complete TARCS algorithm before contributing. Documentation,
examples, accessibility, UI polish, connectors, SDKs, deployment templates and evaluation tools
are all valuable entry points. Start with a `good first issue` or `help wanted` issue whose status
is `ready`.

## Choose a contribution path

| Area | Good first contribution | Additional expectations |
| --- | --- | --- |
| Documentation | Quickstarts, troubleshooting, diagrams, translations | Verify every command in a clean environment |
| Console/UI | Accessibility, responsive behavior, empty states | Run TypeScript, formatting and production-build checks |
| Data sources | Synthetic fixtures, connector documentation | Define pagination, checkpoint, deletion, ACL and secret handling |
| SDKs | Typed examples and generated clients | Keep governance decisions on the server |
| Evaluation | Synthetic cases and reporting tools | State licenses, seeds, corpus construction and limitations |
| Governance/security | Adversarial regression tests | Explain the threat model; maintainer design review is required |

Ask on the issue before starting a large connector, SDK or governance change. This avoids parallel
implementations and ensures the security boundary is agreed before code is written.

## Maintainer-friendly collaboration map

The maintainer can usually complete onboarding copy, synthetic demos, console empty states,
accessibility fixes, bilingual documentation and contract tests independently. Collaboration is
especially valuable for real-world connector ownership, mobile/accessibility testing with new
users, security threat-model review, typed SDK maintenance and design-partner evaluation. Keep
the first contribution small and measurable; a screenshot, fixture, failing test or verified
quickstart is a good starting point.

## Local setup

Backend and documentation changes:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,api,mcp,integrations]'
ruff check src tests
ruff format --check src tests
pytest -q
```

Console changes require Node.js 22:

```bash
cd console
npm ci
npm run format:check
npm run typecheck
npm run build
```

The console build writes to `src/tarcsmem/console_dist/`. Commit both source changes and the
deterministic compiled output; CI rejects a stale bundle.

## Before opening a pull request

1. Do not include customer documents, credentials, PII, screenshots of internal systems or paid datasets.
2. Add or update tests for every behavior change, especially status, time, conflict, ACL, classification or abstention behavior.
3. Run the relevant backend and/or console checks listed above.
4. Explain the threat model and evaluation impact for security, retrieval or LLM changes.

## Design expectations

TARCS-Mem is policy-first: generation must not bypass admission, access controls, valid time, conflict resolution, evidence selection or the cloud-egress gate. Keep provider SDKs optional and preserve the dependency-light core.

For benchmarks, state the corpus, candidate construction, qrels, cutoffs, random seeds, hardware and limitations. Do not present a bounded candidate-pool result as a full-corpus leaderboard result.

## Issues and pull requests

Use the issue templates for reproducible bugs and proposals. Keep a pull request focused and link
the issue it addresses. Include screenshots for visible UI changes, but never screenshot internal
systems or customer data. Maintainers may ask for an adversarial test when a change affects data
isolation, sensitive-content handling or evidence grounding.

Pull requests should state:

- the user problem and non-goals;
- the governance/security impact;
- tests and commands that were run;
- compatibility or migration impact;
- documentation updated for user-visible behavior.

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
