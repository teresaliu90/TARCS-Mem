# TypeScript API smoke client

This Node.js 22 example references the seeded `sales-v2` governed memory, reads its audit
history, queries with a business date, and prints the outcome, citations, trace ID, and answer ID.
It explicitly accepts `answered` or `abstained` and exits safely on HTTP or contract errors.

The server remains the policy authority. The client cannot mark a memory authoritative, change
admission/conflict decisions, or bypass the server's tenant, role, time, status, and citation
checks. `tenant_id` and `roles` are local-demo inputs only; production must derive them from a
verified OIDC/SSO identity at a trusted gateway.

## Run from a clean Node.js 22 environment

First start the seeded FastAPI console from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[api]'
tarcsmem seed --db ./data/tarcsmem-demo.db --if-empty
tarcsmem serve --db ./data/tarcsmem-demo.db --port 8000
```

In a second terminal:

```bash
cd examples/typescript-client
npm ci
npm run typecheck
npm run smoke
```

The example intentionally uses Node 22's built-in type stripping, so the clean path has no
third-party runtime or build dependency. `typecheck` verifies erasable TypeScript syntax; the
smoke run performs required-field and outcome checks against the live v0.8 API contract.

No secret is embedded. For an API-key-enabled server, set `TARCSMEM_API_KEY` in the shell. You
may also set `TARCSMEM_BASE_URL`, `TARCSMEM_TENANT_ID`, or `TARCSMEM_MEMORY_ID`. Do not commit
real tokens or customer identifiers.

Expected output contains only the repository's synthetic policy fixture and resembles:

```text
governed_memory: {"id":"sales-v2","status":"verified_active",...}
record_audit: {"record_id":"sales-v2","events":[...]}
query_result: {"outcome":"answered","citations":["POLICY-SALES-2026-07#1"],"trace_id":"..."}
```

Run the combined Python/API/TypeScript check from the repository root with:

```bash
TARCSMEM_RUN_TYPESCRIPT_SMOKE=1 ./scripts/verify_quickstart.sh
```
