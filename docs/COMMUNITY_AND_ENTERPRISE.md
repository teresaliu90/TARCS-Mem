# Community and Enterprise Direction

[中文版](COMMUNITY_AND_ENTERPRISE_CN.md)

TARCS-Mem is intentionally useful before any commercial relationship exists. The
open-source repository is the Community Edition (CE): a self-hosted reference
implementation that teams can evaluate, adapt and run with synthetic or approved data.
The commercial opportunity is built around operating TARCS-Mem reliably at enterprise
scale, integrating it with an organization's identity and controls, and helping a team
prove outcomes. It is not built by removing the core governance semantics from CE.

This document describes direction, not a promise that every planned item already exists.
Rows marked **planned** require design-partner evidence before implementation or pricing.

## Edition promise

| Capability | Community Edition (MIT, available now) | Enterprise or paid service (planned / service-led) |
| --- | --- | --- |
| Governance core | GuardWrite, GuardRead, TARCS ranking, time/version/conflict handling, abstention and citation verification | Custom policy design, threat-model review and migration support |
| Security baseline | Tenant fields, role ACLs, classification labels, credential blocking, PII redaction and cloud-egress gate | OIDC/SSO, SCIM, verified identity claims, enterprise RBAC and policy administration |
| Storage and deployment | SQLite, Docker, local API and the v0.8 governance console | PostgreSQL/HA, multi-tenant control plane, backup/restore runbooks and managed upgrades |
| Integrations | MCP v2, OpenAI-compatible gateway, LangChain/LlamaIndex, Qdrant and Confluence Cloud | SharePoint, ServiceNow, Salesforce and private-workflow connectors; connector maintenance and SLAs |
| Observability | Privacy-safe traces, Prometheus metrics and local audit history | SIEM/OTLP export, retention/legal hold, compliance evidence packs and operational dashboards |
| Evaluation | Synthetic governance cases and the checked-in bounded FiQA report | Organization-specific quality, risk and cost evaluations with repeatable reports |
| Support | Public issues, documentation and community discussion | Paid pilot, architecture review, private deployment, training, support and SLA |

The exact enterprise scope should be negotiated from a real deployment need. Avoid calling a
feature “enterprise” merely because it is useful: a capability belongs in a paid service when
it requires private infrastructure, continuous operations, organization-specific integration,
or a support/compliance obligation.

## Licensing and packaging

- Keep the current governance core MIT-licensed while adoption and API contracts are still
  evolving.
- Put a hosted control plane, managed operations and organization-specific connectors in a
  service or a separately distributed enterprise package. Do not imply that these planned
  features are present in the public repository.
- Keep optional integrations replaceable and documented. Community users must be able to run a
  complete local path without a vendor account.
- If a future package needs a different license, publish its boundaries and dependency graph
  clearly; do not quietly change the license of existing core files.
- Commercial support, paid pilots and consulting can start before a proprietary package exists.
  They are service revenue, not a reason to weaken CE.

MIT permits forks and commercial use. The defensible value is therefore trust, compatibility,
operational know-how, maintained integrations and evidence from real deployments, rather than
trying to make the open core artificially incomplete.

## What the maintainer can finish independently

These are high-leverage, bounded tasks that do not require another company's systems:

1. Make the first-run console flow a three-step path: seed demo data, run a governed query, then
   inspect the decision trace.
2. Add empty states, keyboard navigation, visible focus, responsive layouts and Chinese/English
   labels. Keep screenshots and a 60–90 second synthetic-data walkthrough current.
3. Publish copy-paste examples for the API, MCP, OpenAI-compatible gateway and one framework
   adapter, with a small troubleshooting page.
4. Add connector contract tests, synthetic fixtures, an OpenAPI artifact and generated client
   scaffolding before adding more connectors.
5. Keep release notes, security boundaries, benchmark limitations and a small contributor
   backlog current. Every issue should have a user, a definition of done and a difficulty label.

## Where collaboration is worth more than solo implementation

- **Design partners:** validate one painful workflow, provide sanitized examples and measure
  stale-answer rate, review time, citation coverage or cloud-egress incidents.
- **Frontend contributors:** test the console with new users and improve accessibility,
  information hierarchy and visual regression coverage across desktop and mobile.
- **Connector maintainers:** own API pagination, checkpointing, deletion, ACL mapping and terms
  of service for a source they use in practice.
- **Security and compliance reviewers:** challenge the identity boundary, retention behavior,
  key management and audit export with a concrete threat model.
- **SDK and evaluation contributors:** maintain typed clients, examples and reproducible tests in
  the languages and datasets their communities already use.

The first external ask should be small: a 30-minute feedback session followed by a two-week,
synthetic-first or sanitized design-partner pilot. Do not request customer data or a broad
integration before the success measure and data boundary are written down.

## Pilot-to-paid path

1. Recruit three to five AI engineers who operate a RAG or Agent system. Show the same synthetic
   console demo to each person and ask where stale, unauthorized or weakly cited memory currently
   causes rework.
2. Select one workflow and record a baseline. Examples: policy-answer freshness, review queue
   time, citation completeness, or blocked sensitive-data egress.
3. Run CE against synthetic data first, then approved sanitized data. Keep identity, retention
   and export decisions explicit in the pilot notes.
4. Publish an anonymized case study only with written permission. A paid pilot can cover setup,
   connector work, evaluation and training while the CE remains public.
5. Productize repeated operational needs as hosted or separately packaged capabilities only after
   at least two design partners report the same problem.

## Community conversion loop

The public project should make the next useful action obvious: run the demo, open a good-first-
issue, add a synthetic connector fixture, or share a measured failure case. Track activation
(first governed answer), retained users (second-week use), contributor pull requests and pilot
outcomes. GitHub stars are useful for discovery but are not a substitute for these measures.
