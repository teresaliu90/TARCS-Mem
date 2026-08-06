# TARCS-Mem Roadmap

This roadmap communicates direction, not guaranteed delivery dates. Security, tenant isolation,
business-time semantics and fail-closed citation behavior take priority over feature count.

## Six-month success measures

- A new user reaches the first governed answer in under 10 minutes.
- At least five external contributors merge a documentation, UI, connector or SDK pull request.
- Three to five enterprise AI engineers complete structured product feedback.
- At least one controlled design-partner pilot produces an anonymized, publishable case study.
- Every new connector passes shared contract tests and uses synthetic fixtures.

## Months 1–2 — Onboarding and contribution surface

### Core and quality

- Freeze and document the v0.8 public memory, query and review schemas.
- Add contract tests for console APIs and connector invariants.
- Publish a versioned OpenAPI artifact for SDK generation.
- Consolidate current-version references, screenshots and release notes.

### Ecosystem

- Publish a connector interface proposal and synthetic fixture kit.
- Add a one-click synthetic-data demo deployment blueprint.
- Scaffold a generated TypeScript client.
- Maintain five to eight well-scoped `good first issue` tasks.

### Community

- Release a 60–90 second v0.8 console demo and two verified Quickstarts.
- Invite five enterprise AI engineers to structured feedback sessions.
- Publish one English launch article and one Chinese technical introduction.
- Establish a monthly issue-triage and contributor update rhythm.

## Months 3–4 — Design-partner integrations and evidence

### Core and quality

- Add a reusable, license-aware governance evaluation schema.
- Benchmark latency and abstention behavior under realistic record counts.
- Define the verified-identity boundary for OIDC/SSO pilots.
- Add an optional privacy-safe OTLP exporter.

### Ecosystem

- Complete one community-prioritized connector: Notion or GitHub documentation.
- Prototype pgvector while preserving pre-ranking governance constraints.
- Publish the TypeScript SDK with two copy-paste examples.
- Document a persistent storage deployment for controlled pilots.

### Community

- Run one narrowly scoped design-partner pilot using sanitized or synthetic-first data.
- Publish connector author documentation and an office-hour recording.
- Present the architecture to one RAG/Agent, Python or AI security community.
- Recognize contributors in release notes and a contributors section.

## Months 5–6 — Production-readiness evidence and repeatable adoption

### Core and quality

- Publish v1-readiness criteria for schema stability, migrations and threat modeling.
- Verify backup/restore and audit export for pilot deployments.
- Evaluate an external policy-engine adapter boundary without moving decisions into clients.
- Expand adversarial tests for cross-tenant access, stale policy, citation forgery and cloud egress.

### Ecosystem

- Complete a second enterprise connector selected from pilot evidence.
- Graduate the TypeScript SDK and decide whether demand justifies a maintained Go client.
- Add Helm/Kubernetes examples only after a real deployment requires them.
- Publish a tested compatibility and maturity matrix.

### Community

- Publish one anonymized case study with measurable before/after outcomes.
- Hold a roadmap review with contributors and design partners.
- Tag v0.9 or a v1.0 release candidate only when documented exit criteria pass.
- Define sustainable hosted, enterprise-support or paid-pilot options while preserving a useful
  open governance core.

## Not planned without evidence

- A general-purpose chatbot builder.
- Multi-agent complexity without a demonstrated governance use case.
- GraphRAG as a default dependency.
- Provider-specific logic inside the dependency-light governance core.
- Production claims without external security and operational evidence.

## How to influence this roadmap

Open a feature proposal describing the user, current failure mode, threat model and measurable
success criteria. Maintainers prioritize repeated design-partner needs over feature count.
