# TARCS-Mem Next-Stage Upgrade Plan

Status: **design and product plan for the next release cycle**

Audience: maintainers, enterprise AI engineers, security reviewers, frontend contributors and
potential design partners

TARCS-Mem is currently a high-quality personal open-source project and an early-Alpha enterprise
AI governance reference implementation. The next stage should make its difference obvious:
memory systems store and retrieve context; TARCS-Mem governs which context is trusted, active,
authorized, timely, citable and auditable.

This plan borrows useful patterns from three open-source families without copying their code or
licenses:

| Pattern family | Useful pattern to learn from | TARCS-Mem's adaptation |
| --- | --- | --- |
| Memory OS and long-term memory frameworks | layered memory, lifecycle management, graph/semantic recall, MCP access | put an explicit governance decision and evidence lineage around every durable memory transition |
| Enterprise RAG and context platforms | connector catalogs, ingestion/index status, pipeline observability, deployment profiles | make ACL, classification, business-time and conflict constraints first-class pipeline stages |
| AI governance and audit frameworks | policy templates, control evidence, asset inventories, accountable approvals and risk registers | bind policy versions and human decisions to memory versions, evidence packs and final answers |

The target pipeline remains:

```text
Documents / conversations / approval records
                  |
            GuardWrite
 extract -> schema validate -> admission -> conflict resolver
                  |
  append-only audit events + active memory projection
                  |
User question -> hybrid retrieval -> RRF -> TARCS constraints/ranking
                  |                         |
                  |                    token-budget MMR
                  v                         v
              evidence pack -> verification -> answer / clarify / abstain
```

## Status vocabulary

- **Current:** available in the v0.8 reference implementation.
- **Next:** a bounded change that can be implemented and tested in the community repository.
- **Future:** requires production identity, private infrastructure, repeated pilot demand or a
  separate enterprise service.

---

# Part I — Architecture Paradigms and Meaningful Innovation

## 1. Governance-native memory OS

**Idea:** Treat memory as a governed state machine, not an undifferentiated vector collection.
Every candidate has provenance, business validity, observation time, classification, access
scope, conflict domain and an explicit state such as `pending`, `verified_active` or
`superseded`.

**Pattern connection:** Memory OS projects commonly separate short-term context, durable memory,
semantic recall and lifecycle operations. TARCS-Mem adds an admission and conflict boundary before
durable memory can be used as enterprise evidence.

**Problem solved:** Prevents a plausible chat claim or model inference from silently becoming a
policy fact. It also makes “why is this memory active?” answerable without inspecting embeddings.

**Differentiator:** The durable unit is not only a memory node; it is a memory decision with source,
policy, evidence and lineage.

## 2. Policy DSL with replayable GuardWrite decisions

**Idea:** Represent schema, admission and conflict rules as versioned policy bundles. A write
decision can be replayed against a redacted fixture set to explain what changed when a policy was
updated.

**Pattern connection:** AI governance frameworks often use control catalogs, rule templates and
accountable approvals. TARCS-Mem applies the same discipline at the memory-write boundary and
preserves the evaluated policy digest next to the memory transition.

**Problem solved:** Avoids hard-coded source thresholds spreading through connectors and makes
different profiles possible for enterprise policy, finance research and scientific notes.

**Differentiator:** Policy evaluation is attached to memory state transitions and can be compared
against prior decisions. A policy cannot grant access, bypass identity or disable mandatory audit
requirements through an untrusted request.

## 3. Audit-aware hybrid RAG

**Idea:** Retrieval returns an evidence pack with selection and exclusion reasons, not just a list
of chunks. The answer is linked to the exact memory versions, projection checkpoint, retrieval
policy and verification outcome used to produce it.

**Pattern connection:** Enterprise RAG platforms commonly expose connector and retrieval status;
memory systems commonly expose recall or timeline views. TARCS-Mem combines these into a
decision-centric evidence chain.

**Problem solved:** A compliance reviewer can answer “which version was used, who could access it,
why was it ranked, which policy was active, and why was the answer returned?”

**Differentiator:** ACL, classification, valid-time, conflict and citation checks are hard
constraints before generation, not dashboard annotations after the fact.

## 4. Policy plane and data plane separation

**Idea:** Keep governance policies, identity claims, audit events and evaluation fixtures in a
policy plane, while memories, embeddings and source content live in a data plane. The data plane
cannot weaken policy decisions supplied by the policy plane.

**Pattern connection:** Enterprise RAG deployments separate control/configuration services from
connectors and serving paths. TARCS-Mem makes that boundary explicit so a connector cannot choose
its own authority or cloud-egress behavior.

**Problem solved:** Reduces configuration drift across tenants and makes a future hosted control
plane possible without moving the dependency-light core into a vendor-specific product.

**Differentiator:** The policy plane returns signed/versioned decisions and constraints, while the
data plane remains replaceable: SQLite, PostgreSQL, Qdrant or another approved store.

## 5. Domain profiles and evaluation-driven governance

**Idea:** Ship small, testable profiles instead of a universal policy mega-config. A profile
contains source trust, time semantics, classification defaults, retrieval weights, verification
rules, review obligations and benchmark fixtures.

**Pattern connection:** Mature RAG systems expose deployment profiles and connector templates;
governance frameworks expose control families. TARCS-Mem should combine them into profiles that
are easy to evaluate and hard to misconfigure.

**Problem solved:** A finance research workflow and an internal policy assistant should not share
the same freshness, source authority or citation requirements by accident.

**Differentiator:** Each profile ships with expected abstention cases, adversarial fixtures and a
known limitation statement, not only YAML defaults.

## Highest-value directions to implement first

Prioritize two directions in the open-source core:

1. **Replayable GuardWrite policy bundles:** small enough to test locally and valuable to every
   connector and deployment.
2. **Answer-centric evidence chains:** immediately visible in the console and useful even before
   a full event-sourced projection exists.

Do not begin by implementing every memory type, graph database, SSO provider or enterprise
connector. Those are integration surfaces, not the project's strongest differentiator.

## GuardWrite policy engine sketch

```python
class PolicyBundle(BaseModel):
    bundle_id: str
    version: str
    digest: str
    schema_version: str
    structural_rules: list[StructuralRule]
    admission_rules: list[AdmissionRule]
    conflict_rules: list[ConflictRule]
    mandatory_baseline: MandatoryBaseline

class GovernancePolicyEngine(Protocol):
    def validate_bundle(self, bundle: PolicyBundle) -> BundleValidation: ...
    def evaluate_schema(self, candidate: MemoryItemCandidate, bundle: PolicyBundle) -> SchemaResult: ...
    def evaluate_admission(
        self, candidate: MemoryItemCandidate, context: WriteContext, bundle: PolicyBundle
    ) -> PolicyDecision: ...
    def resolve_conflict(
        self, incoming: MemoryItemCandidate, existing: list[MemoryProjection], bundle: PolicyBundle
    ) -> ConflictResolutionResult: ...
    def replay(self, fixture_set: FixtureSet, bundle: PolicyBundle) -> ReplayReport: ...
```

Illustrative policy format:

```yaml
apiVersion: tarcsmem.io/v1alpha1
kind: MemoryGovernancePolicy
metadata:
  name: enterprise-policy
  version: 2026-08-01
spec:
  defaults:
    admission: review
    conflict: review
    missing_identity: reject
  mandatoryBaseline:
    requireTenant: true
    requireAudit: true
    forbidModelSelfApproval: true
    allowedClassifications: [public, internal, confidential, restricted]
  admission:
    - id: activate-approved-policy
      when:
        all:
          - {path: source.source_type, equals: official_policy}
          - {path: evidence.count, gte: 1}
          - {path: extraction_confidence, gte: 0.75}
          - {path: durable_value, gte: 0.70}
      decision: {outcome: accept, target_state: verified_active, authority: 1.0}
    - id: model-inference-needs-external-evidence
      when: {path: source.source_type, equals: model_inference}
      decision: {outcome: reject, reason: MODEL_INFERENCE_NOT_AUTHORITATIVE}
  conflict:
    scope: [tenant_id, conflict_key]
    rules:
      - id: newer-higher-authority
        when: {all: [incoming.has_valid_from, incoming.authority_gt_existing]}
        decision: supersede
      - id: equal-authority-ambiguous
        when: {path: conflict.overlap, equals: true}
        decision: review
```

Policy evaluation requirements:

- structural validation remains code-owned and cannot be disabled by YAML;
- unknown fields, predicates, states and rule IDs fail bundle validation;
- `reject > review > accept` is the combination precedence;
- tenant overlays may tighten but never weaken mandatory identity, audit or classification rules;
- policy bundles are signed or approved by an operator before activation;
- dry-run replay compares the new bundle with the active bundle over synthetic fixtures;
- every decision stores bundle ID, version, digest, reason codes and normalized input hash;
- policy files never execute arbitrary Python, shell commands or tenant-provided templates.

## Audit ledger and projection sketch

```python
class AuditLedger(Protocol):
    def append(self, event: AuditEvent, expected_sequence: int) -> AppendReceipt: ...
    def stream(self, aggregate_id: str, after: int = 0) -> list[AuditEvent]: ...
    def search(self, filters: AuditFilters, cursor: str | None = None) -> AuditPage: ...
    def verify(self, aggregate_id: str) -> ChainVerificationResult: ...

class MemoryProjection(Protocol):
    def get(self, memory_id: str, as_of: date | None = None) -> MemoryView | None: ...
    def list(self, principal: VerifiedPrincipal, filters: MemoryFilters) -> Page[MemoryView]: ...
    def checkpoint(self) -> ProjectionCheckpoint: ...
    def rebuild(self, snapshot: Snapshot | None = None) -> RebuildReport: ...
```

The ledger is the historical decision record; the projection is a disposable query view. A
projection row must include the last applied event position and enough provenance to rebuild or
verify each field. A snapshot is valid only when its hash, policy schema and ledger position pass
verification. This permits a local mutable table in the short term while preserving a path to an
immutable production ledger later.

## Architecture paradigms — README draft

```markdown
### Architecture paradigms

TARCS-Mem aligns with two communities without becoming another memory SDK or RAG engine. From
memory systems it borrows layered lifecycle management and provider-neutral recall. From
enterprise RAG and governance frameworks it borrows connector contracts, policy profiles and
accountable audit evidence.

Its distinctive combination is governance-native memory: GuardWrite decides whether a claim may
become active, an append-only decision history preserves why, and an active projection serves
current reads. GuardRead then applies identity, classification, business-time and conflict
constraints before TARCS ranking and evidence-pack verification. The result is an auditable answer,
a clarification request or a deliberate abstention—not an unsupported completion.
```

---

# Part II — Console and Usability Upgrade

## Console product principle

The console should feel like a compact governance operations workspace, not a decorative RAG
demo. Every page should answer one of three questions:

1. **What needs attention?** pending reviews, policy failures, connector failures, egress blocks.
2. **What decision was made?** active memory state, evidence selection, policy and audit lineage.
3. **What can I safely try next?** a scenario template, a governed query or a connector dry run.

The current v0.8 pages are `Overview`, `Security sandbox`, `Trusted memories`, `Review workspace`,
`Trace and audit`, and `Integration center`. The following work improves those pages before adding
another navigation category.

## Wizard paths

### Wizard A — Enterprise knowledge-base governance

**Goal:** reach a first governed answer with synthetic or approved Confluence data.

1. **Choose a profile:** show `enterprise-policy` defaults, data classification and identity
   prerequisites. The user must acknowledge that demo roles are not production identity.
2. **Connect a source:** show connector health, last sync, source count, ACL mapping status,
   checkpoint and deletion behavior. Provide a synthetic fixture path when credentials are absent.
3. **Review GuardWrite policy:** show source classes, activation thresholds, pending-review rules
   and conflict behavior. Offer a dry-run over six records before activation.
4. **Inspect the write result:** show admitted, pending and rejected counts plus one memory lineage.
5. **Ask a question:** display answer/clarify/abstain, selected evidence, excluded reasons and the
   exact business date used.
6. **Open the audit chain:** link answer to evidence pack, memory versions, policy digest and
   approval events.

Primary panels: profile checklist, connector health, policy preview, review queue, answer evidence
pack and audit timeline.

### Wizard B — Financial document governance

**Goal:** evaluate freshness, source authority, licensing and numerical evidence support.

1. Select a synthetic SEC/filing fixture or an approved licensed source.
2. Configure source entitlement, filing period, stale-data threshold and cloud-egress policy.
3. Run a retrieval dry run showing SEC, keyword, licensed research and structured-data candidates.
4. Compare a fresh filing with an older filing and show why the older version was excluded.
5. Ask a numerical question and inspect citation membership, table support and abstention behavior.
6. Export a privacy-safe evaluation report containing metrics and policy versions, not licensed text.

Primary panels: source entitlement, freshness timeline, retrieval debugger, numerical verification,
risk notice and exportable evaluation summary.

### Wizard C — Agent memory debugging

**Goal:** help an Agent engineer find why a response was answered, clarified or blocked.

1. Paste a synthetic question or select a saved test case.
2. Show route selection, source calls, ACL/tenant filters, fusion, TARCS scores and MMR budget.
3. Show the evidence pack and answer verification result.
4. Compare “governed path” with an intentionally weak baseline without exposing restricted text.
5. Save the case as a regression fixture with expected outcome and reason codes.

Primary panels: request context, pipeline timeline, candidate table, selected evidence and fixture
editor.

## Audit timeline and memory projection view

The memory detail view should combine the current projection with a readable timeline:

```text
source received -> security scan -> schema result -> admission decision
       -> conflict comparison -> human review -> active/superseded state
       -> selected for answer -> citation/egress verification
```

Timeline events should show timestamp, actor type, policy version, reason code and linked memory or
answer ID. The default view hides raw payloads and displays hashes/references. An “inspect lineage”
action expands only fields permitted by the caller's role.

The answer view should group evidence into:

- **Used:** selected memory ID, source ref, validity, classification, TARCS/MMR scores and reason;
- **Considered but excluded:** ACL, stale, pending, conflict, low relevance or token-budget reason;
- **Governance:** retrieval policy, GuardWrite policy, projection checkpoint and verification state;
- **History:** write events, supersession and named approval records.

## UX improvement backlog

| Priority | Area | Change | Definition of done |
| --- | --- | --- | --- |
| P0 | Onboarding | Add a three-step first-run checklist to Overview | A new user reaches one governed answer without reading internal docs |
| P0 | Empty states | Add actionable empty states for no memories, no reviews, no traces and no connectors | Every empty state has one safe next action and a link to a scenario |
| P0 | Audit | Add answer-centric evidence-chain entry from Sandbox and Trace | A user can reach write lineage from a result without copying IDs |
| P1 | Retrieval debugger | Add candidate stages and exclusion reasons | Source, fusion, constraints, ranking and MMR are visually distinct |
| P1 | Accessibility | Keyboard navigation, visible focus, labels, table semantics and reduced-motion support | Console passes an automated accessibility smoke check and manual keyboard pass |
| P1 | Responsive | Review 320px, 768px and desktop layouts | No horizontal overflow; evidence tables remain usable on small screens |
| P1 | Internationalization | Extract labels and support English/Chinese locale selection | Governance reason codes remain stable while UI labels are translated |
| P2 | Visual regression | Add stable synthetic fixtures and screenshot checks | Main pages have deterministic screenshots across two viewport sizes |
| P2 | Saved cases | Save synthetic regression questions and expected outcomes | A case can be rerun after policy, connector or ranker changes |

## Navigation proposal

Keep the current top-level navigation and improve its information architecture:

```text
Overview
  ├─ First-run checklist
  ├─ Governance health
  └─ Recent attention items
Test and debug
  ├─ Safety sandbox
  ├─ Retrieval debugger
  └─ Saved regression cases
Memory governance
  ├─ Trusted memories
  ├─ Review workspace
  └─ Memory lineage
Evidence and audit
  ├─ Trace explorer
  ├─ Answer evidence chains
  └─ Audit search
Integrations
  ├─ Connectors
  ├─ Models and egress
  └─ Session/API configuration
```

Do not add a generic “analytics” page until a real operator needs a metric that cannot be answered
by governance health, traces or audit search.

## English UI copy drafts

**No data source**

> No governed source is connected yet. Start with the synthetic demo, or connect an approved
> source to import records through GuardWrite.

**No policy profile**

> No policy profile is active. Choose a reviewed profile before accepting new memory.

**No audit history**

> There is no audit history for this memory. It may not have been ingested by this workspace, or
> your role may not include lineage access.

**Projection is catching up**

> The latest write is committed, but the read projection is still catching up. Refresh after the
> checkpoint advances.

**Evidence unavailable**

> No evidence passed identity, status, business-time and conflict checks. The system abstained.

**Cloud egress blocked**

> Selected evidence includes a classification that this provider is not allowed to receive. No
> model call was made.

**Connector checkpoint stalled**

> The connector has not advanced since {timestamp}. Review credentials, rate limits, deletion
> handling and the last safe checkpoint before retrying.

## Console & UX overview — README draft

```markdown
### Console and UX overview

The governance console is the fastest way to understand TARCS-Mem without connecting a model.
It uses synthetic records to show GuardWrite admission, conflict handling, human review, GuardRead
filtering, evidence selection, citation verification and privacy-safe audit traces.

Unlike a generic RAG dashboard, the console does not stop at connector status or retrieved chunks.
It shows why a memory became active, why another version was excluded, which policy and business
date were applied, and whether the final answer should be returned or abstained. The same screens
work with a controlled pilot once verified identity, retention and source boundaries are configured.
```

---

# Part III — Production Readiness Roadmap

## Phase 1 — PoC-ready

**Purpose:** demonstrate one bounded workflow on one controlled node using synthetic or approved
data.

### Reference topology

```text
Browser / local Agent
        |
  TLS-capable gateway (optional for local PoC)
        |
FastAPI TARCS-Mem service
   |             |             |
SQLite       Qdrant       local/approved model
   |
privacy-safe metrics and local audit history
```

### Required capabilities

- one named tenant and a small role set;
- API key or local user mapping for the PoC, explicitly not a production identity claim;
- GuardWrite, review, GuardRead, citation verification and cloud-egress defaults;
- backup of the SQLite file and a documented reset procedure;
- synthetic fixture set, expected answers, abstentions and conflict cases;
- health/readiness, request IDs, rate limits and idempotent writes;
- a short runbook for credentials, failed imports, blocked egress and restore.

### Minimum documentation directory

```text
docs/
  QUICKSTART.md                 # first governed answer
  CONSOLE.md                    # operator walkthrough
  PRODUCTION_DEPLOYMENT.md      # bounded pilot controls
  SECURITY.md                   # threat model and limits
  OBSERVABILITY.md              # metrics and privacy boundary
  EVALUATION.md                 # fixtures, metrics and limitations
  RUNBOOK.md                    # failure and restore procedures
```

### Exit evidence

The PoC is ready when a new operator can reproduce a governed answer, an abstention, a conflict
review and an egress block from a clean environment, and can restore the data store from a tested
backup.

## Phase 2 — Pilot-ready

**Purpose:** support a small design-partner deployment with verified identity, persistent storage
and operational ownership.

### OIDC/SSO design

```text
OIDC provider -> gateway/token validator -> VerifiedPrincipal
                                      |
                         policy context + request context
                                      |
             GuardWrite / GuardRead / Audit query authorization
```

Proposed modules:

- `IdentityAdapter`: validates issuer, audience, signature, expiry and key rotation;
- `ClaimsMapper`: maps subject, organization, tenant, groups and entitlements to an internal
  `VerifiedPrincipal` without trusting request-body roles;
- `PolicyContext`: carries principal snapshot hash, authentication context, purpose and policy
  bundle version;
- `AuthorizationBoundary`: enforces tenant, role, classification and audit-query permissions;
- `IdentityAuditAdapter`: records authentication context and claim-mapping version as hashes or
  opaque identifiers, never raw tokens.

GuardWrite uses identity to attribute who or which service submitted a claim; it must still derive
authority from source policy, not from a user's requested role. GuardRead uses verified claims for
source-side filtering and records the principal snapshot hash in the evidence pack. Audit queries
apply the same authorization boundary as memory reads, with stricter permissions for raw lineage.

### Multi-tenant and organization isolation

Every `MemoryItem`, `PolicyBundle`, `AuditEvent`, `EvidencePack`, connector checkpoint and
projection row carries `organization_id` and `tenant_id`. A safe default is:

```text
organization_id -> tenant_id -> workspace/project -> memory/connector
```

Isolation rules:

- tenant is a required routing key, not an optional filter;
- storage partitions and indexes include tenant IDs;
- vector queries push tenant filters into the vector store;
- policy bundles are resolved by organization/tenant scope with an explicit inheritance chain;
- connector credentials and checkpoints never cross tenant scope;
- audit search requires an authorized tenant scope and emits access events;
- cross-tenant operations are explicit service-admin workflows with separate approval.

### Pilot topology and resilience

```text
Load balancer / gateway
          |
  2+ stateless API workers
      |          |
Managed PostgreSQL   Qdrant cluster
      |
Immutable audit sink + metrics/traces
      |
Object storage backups and restore drills
```

Pilot requirements include migration scripts, connection pooling, queue-backed connector sync,
dead-letter handling, rolling deployment, backup encryption, restore verification and a tested
runbook for a failed projection worker. A pilot need not begin with Kubernetes; it does need clear
ownership for data, identity, operations and incident response.

### Exit evidence

The pilot is ready when OIDC claims are verified end to end, two tenants cannot read each other's
memory or audit metadata, a restore drill succeeds, connector retries are idempotent, and measured
latency/abstention/egress metrics are reviewed by the design partner.

## Phase 3 — Production-ready

**Purpose:** operate under an organization's security, compliance, availability and support
obligations.

### SIEM integration

Export privacy-safe security and governance events, not raw prompts or document text. Prioritize:

- authentication failures, claim-mapping failures and privilege changes;
- cross-tenant denials and repeated ACL denials;
- GuardWrite rejects, policy changes, human approvals and conflict escalations;
- cloud-egress allowed/blocked decisions and classification categories;
- citation-verification failures, unusual abstention shifts and connector credential failures;
- audit-chain verification failures, projection rollback and restore events.

Each export carries event ID, tenant scope, timestamp, actor type, policy digest, reason codes,
correlation ID, severity and integrity metadata. A SIEM adapter must support backpressure and
replay without changing the source ledger.

### KMS and secret management

```text
Secret manager -> short-lived connector/model credentials
KMS/HSM        -> data-key wrapping, audit signing keys, backup encryption
TARCS-Mem      -> key references and rotation version, never key material
```

Use envelope encryption for source payloads and sensitive audit references. Rotate data keys by
policy, keep signing-key rotation verifiable against historical signatures, and define what
happens to encrypted payloads under deletion or legal hold. Cloud-provider API keys belong in a
secret manager and must never enter evidence packs, metrics or screenshots.

### Capacity and load planning

Measure each stage separately:

| Dimension | PoC baseline | Pilot benchmark | Production decision |
| --- | --- | --- | --- |
| active memories | 10k synthetic records | 100k–1m representative records | shard/partition strategy and migration plan |
| writes | burst and idempotent retry tests | sustained connector throughput | queue sizing and backpressure |
| reads | single-user P95 | concurrent tenant-scoped P95 | autoscaling and cache policy |
| audit events | replay correctness | export lag and chain verification | immutable retention and search tier |
| evidence pack | token budget and citation checks | provider/model latency | cost and context policy |

These are benchmark stages, not product guarantees. Record hardware, corpus, concurrency,
connector rate limits, model provider, cache state and failure mode. Capacity claims should be
published only after repeatable tests and an operational margin.

### Production exit evidence

Production-ready means documented schema/migration compatibility, external security review or
equivalent threat-model evidence, verified restore, SIEM/KMS integration, load and chaos results,
alert/runbook ownership, incident response, retention/legal-hold behavior and a support policy.
It is not established by a successful Docker build alone.

## Current placement in the TARCS-Mem repository

| Concern | Current v0.8 location | Next boundary |
| --- | --- | --- |
| identity and access | `AccessContext`, API key baseline, request-body demo roles | gateway-verified `VerifiedPrincipal` and claim mapper |
| GuardWrite | `TARCSMemoryService.ingest`, `MemoryAdmission`, `ConflictResolver` | policy bundle engine with replay and signed versions |
| audit | `AuditEvent`, SQLite `audit_events`, record audit endpoint | immutable ledger adapter, answer-centric audit queries |
| memory view | SQLite `memories` payload table | event-folded projection with checkpoint and rebuild |
| retrieval | `TARCSRetriever`, optional Qdrant adapter | configured source/fusion/constraint plugins |
| operations | health/readiness, metrics, bounded spans, Docker | distributed telemetry, SIEM/KMS, HA and runbooks |

## Production status and usage boundary — README/PRODUCTION draft

```markdown
### Production status and usage boundary

TARCS-Mem is an early-Alpha governance reference implementation suitable for local evaluation,
synthetic demonstrations and bounded internal or design-partner pilots. It is not a certified
enterprise security product and should not receive regulated, highly confidential or production-
critical data without an organization's own identity, DLP, KMS, retention, monitoring, backup,
restore and security-review controls.

The reference stack demonstrates governed writes, version/conflict handling, access-aware
retrieval, abstention, citation checks and cloud-egress blocking. A production deployment must
replace demo identity inputs, SQLite and local audit history with verified OIDC/SSO claims,
managed storage, immutable audit export, enterprise secrets, operational monitoring and tested
incident/restore procedures.
```

---

# Part IV — Community Maturity and Commercial Potential

## Proposed issue label system

These labels are a proposed public backlog taxonomy; they should be created only after maintainers
agree on names and color conventions.

| Label | Use |
| --- | --- |
| `good first issue` | Bounded work that can be completed without changing governance semantics |
| `help wanted` | Maintainer welcomes an external implementation or investigation |
| `docs` | README, guides, diagrams, examples and translations |
| `ui/ux` | Console information hierarchy, accessibility, responsive behavior and visual polish |
| `data-source` | Connector, checkpoint, deletion, ACL mapping and source terms |
| `integration` | MCP, OpenAI-compatible, LangChain, LlamaIndex or provider adapters |
| `governance-core` | GuardWrite, GuardRead, conflict, policy and projection behavior |
| `audit` | Event schema, lineage, integrity, export and audit queries |
| `security` | Threat model, identity, classification, egress and adversarial tests |
| `production` | Deployment, HA, migration, backup, restore, telemetry and runbooks |
| `evaluation` | Fixtures, benchmarks, regression reports and metric methodology |
| `examples` | Copy-paste samples, notebooks and integration templates |
| `design-partner` | Work requiring validated enterprise feedback or sanitized data |
| `status: ready` | Scope and definition of done are clear enough to start |
| `status: needs-design` | Requires a maintainer or security design decision before coding |

## Issue backlog drafts

1. **Add a three-step first-run checklist to the governance console** — Show seed demo, run a
   governed query and inspect the evidence chain. Labels: `ui/ux`, `good first issue`, `status: ready`.
2. **Add actionable empty states for console pages** — Cover no memories, no reviews, no traces,
   no connector and projection lag. Labels: `ui/ux`, `docs`, `status: ready`.
3. **Add an answer-centric evidence-chain response shape** — Link answer ID, evidence pack,
   selected/excluded reasons and memory lineage. Labels: `audit`, `governance-core`, `status: needs-design`.
4. **Publish a verified Confluence connector contract fixture kit** — Include pagination,
   checkpoint, deletion, ACL and retry cases using synthetic payloads. Labels: `data-source`, `examples`.
5. **Add a retrieval debugger fixture to the console** — Display source candidates, fusion, hard
   filters, TARCS scores and MMR selection. Labels: `ui/ux`, `evaluation`, `status: needs-design`.
6. **Create a policy-bundle schema and dry-run validator** — Validate version, predicates, states,
   mandatory baseline and deterministic precedence without executing arbitrary code. Labels:
   `governance-core`, `security`, `audit`.
7. **Add GuardWrite replay reports for synthetic fixtures** — Compare two policy versions and list
   changed outcomes and reason codes. Labels: `governance-core`, `evaluation`.
8. **Add projection replay and checkpoint consistency tests** — Prove rebuild produces the same
   current memory view after duplicate or reordered delivery. Labels: `audit`, `governance-core`, `production`.
9. **Add verified-principal adapter interfaces** — Define OIDC claim mapping without trusting
   request-body tenant or roles. Labels: `security`, `production`, `status: needs-design`.
10. **Add tenant-isolation contract tests for vector and audit queries** — Test source-side filters,
    projection reads and audit metadata leakage. Labels: `security`, `production`.
11. **Add a privacy-safe SIEM export adapter design** — Define event allow-list, severity mapping,
    backpressure and replay behavior. Labels: `security`, `audit`, `production`.
12. **Add a financial freshness and numerical-citation fixture set** — Use approved synthetic or
    redistributable data and document limitations. Labels: `evaluation`, `examples`, `design-partner`.
13. **Add a TypeScript client smoke example** — Call governed write, query and audit endpoints with
    generated types. Labels: `integration`, `examples`, `good first issue`.
14. **Add responsive and keyboard navigation checks for the console** — Cover 320px, desktop,
    focus order, labels and reduced motion. Labels: `ui/ux`, `good first issue`.
15. **Document a PostgreSQL/Qdrant pilot topology and restore drill** — Include migration,
    backup, restore and rollback evidence requirements. Labels: `production`, `docs`.

## Contributing & Community — README draft

```markdown
### Contributing and community

TARCS-Mem welcomes contributors who improve trustworthy enterprise AI in a concrete way:

- frontend engineers improving onboarding, accessibility and evidence-chain views;
- connector maintainers adding source checkpoints, ACL mapping and deletion safety;
- security and compliance engineers reviewing identity, classification, audit and egress boundaries;
- platform engineers testing deployment, migration, backup, restore and telemetry paths;
- SDK and evaluation contributors maintaining typed examples and reproducible fixtures;
- enterprise AI engineers sharing sanitized failure cases and design-partner feedback.

You do not need to understand the full TARCS algorithm to contribute. Start with a `good first
issue`, a verified quickstart, a synthetic fixture or a focused UI improvement. Changes to
GuardWrite, ACL, conflict, citation, projection or cloud-egress semantics require a threat model,
regression tests and maintainer design review. Never include customer documents, credentials, PII,
internal screenshots or paid datasets.
```

## Commercial paths

### 1. Enterprise PoC and integration services

**MVP:** a two-to-four-week bounded workflow with one connector, one verified success metric, a
synthetic-first evaluation, deployment runbook and an anonymized report format.

**Open source boundary:** governance core, local console, reference connectors, fixtures and
evaluation method remain public.

**Paid boundary:** discovery, architecture review, private connector work, identity integration,
data migration, evaluation execution, training and support responsibility.

This is the fastest path to revenue because it sells outcomes and deployment expertise before a
large proprietary control plane exists.

### 2. Hosted or enterprise operations package

**MVP:** verified OIDC/SSO, multi-tenant organization isolation, managed PostgreSQL/Qdrant,
immutable audit export, SIEM/OTLP integration, KMS/secret management, backups, upgrades and SLA.

**Open source boundary:** a complete local Community Edition with the same core governance
semantics and documented extension contracts.

**Paid boundary:** hosted control plane, private networking, operations, compliance evidence,
retention/legal hold, support and managed connectors. Keep proprietary packages separate from the
MIT core and publish their boundary clearly.

### 3. Governance plugin for existing Agent or research platforms

**MVP:** one stable API/MCP integration, a typed SDK, evidence-pack contract, policy profile and
an evaluation report for a partner platform.

**Open source boundary:** provider-neutral gateway, SDK types, integration examples and synthetic
fixtures.

**Paid boundary:** partner-specific connector, entitlement mapping, deployment, support,
performance tuning and joint evaluation. This route makes TARCS-Mem a governance layer rather
than a competing chatbot or RAG platform.

## Project status and vision — README draft

```markdown
### Project status and vision

TARCS-Mem is a high-quality personal open-source project and an early-Alpha enterprise AI
governance reference implementation. It already demonstrates governed memory writes, version and
conflict handling, access-aware retrieval, abstention, citation verification, MCP/OpenAI-compatible
integration and a working governance console.

The long-term vision is to become an open governance layer that complements memory OS, enterprise
RAG and AI governance ecosystems. TARCS-Mem does not try to replace your model, connector or
Agent framework. It makes their memory and evidence decisions explicit, policy-controlled and
auditable.

Use the Community Edition to run a synthetic demo, evaluate a bounded workflow, propose a
connector or contribute a fixture. Enterprise teams can help shape verified identity, production
operations and domain profiles through sanitized design-partner pilots.
```

## Community conversion loop

The project should make the next safe action obvious:

```text
run synthetic demo -> inspect evidence chain -> open a focused issue
        -> contribute fixture/UI/connector -> share measured failure
        -> design-partner pilot -> publish anonymized evidence
```

Track first governed answer, second-week retention, external pull requests, verified fixtures,
design-partner interviews and pilot outcomes. GitHub stars are useful for discovery but do not
substitute for usage evidence.

## Recommended 90-day sequence

### Days 1–30: make the difference visible

- Add the first-run wizard copy and evidence-chain terminology to the console.
- Publish two scenario profiles and synthetic fixtures.
- Create five ready-to-start issues from the backlog above.
- Record a 60–90 second console walkthrough.

### Days 31–60: prove the architecture with small slices

- Add stable `answer_id`, `evidence_pack_id` and `correlation_id` fields.
- Implement answer-centric audit retrieval before attempting full event sourcing.
- Add one policy-bundle dry-run validator and replay report.
- Interview three to five enterprise AI engineers using the same demo.

### Days 61–90: earn production and commercial evidence

- Run one synthetic-first or sanitized design-partner pilot.
- Measure stale-answer rate, citation completeness, review time or blocked egress.
- Publish an anonymized case study only with written permission.
- Decide which repeated operational need belongs in Community Edition, paid service or neither.
