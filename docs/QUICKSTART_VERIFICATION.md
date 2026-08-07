# Verified clean-environment Quickstart

Last maintainer verification: **2026-08-07**, macOS, Python 3.11-compatible project environment,
Node.js 25 locally; CI pins Python 3.11 and Node.js 22. The critical path is repeated on every
push by `.github/workflows/ci.yml`.

This guide verifies the FastAPI governance console. It does not start the optional Gradio Agent,
download a model, connect a vector database, or require an external credential.

## Reproduce from a clean clone

```bash
git clone https://github.com/teresaliu90/TARCS-Mem.git
cd TARCS-Mem
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[api]'
./scripts/verify_quickstart.sh
```

Expected final line:

```text
PASS: console, governed answer, citation, trace, and both audit paths use synthetic data only.
```

The script creates a temporary SQLite database, seeds exactly six fictional records, opens a
temporary localhost API, verifies `/console/`, executes the **Policy version** scenario, checks
that `sales-v2` was selected instead of the pending meeting note, and reads both answer and record
audit paths. It removes its temporary directory and stops the server on exit.

To include the dependency-free Node.js 22 TypeScript client:

```bash
cd examples/typescript-client
npm ci
cd ../..
TARCSMEM_RUN_TYPESCRIPT_SMOKE=1 ./scripts/verify_quickstart.sh
```

## Manual browser path (under ten minutes)

```bash
tarcsmem seed --db ./data/tarcsmem-demo.db --if-empty
tarcsmem serve --db ./data/tarcsmem-demo.db --port 8000
```

1. Open `http://127.0.0.1:8000/console/`.
2. Confirm the first-run guide says six synthetic records are loaded.
3. Open **安全测试场** and keep **制度版本** selected.
4. Select **查证并解释**.
5. Confirm the citation is `POLICY-SALES-2026-07#1`.
6. Select **查看回答证据链** and inspect policy, lineage, verification, and the explicit
   `chain_verified: false` SQLite notice.

## Troubleshooting

| Symptom | Cause | Safe action |
| --- | --- | --- |
| `Address already in use` | Port 8000 is occupied | Run `tarcsmem serve ... --port 8001`; open `/console/` on 8001 |
| `Install API extras` | FastAPI/Uvicorn were not installed | Activate the venv and run `pip install -e '.[api]'` |
| Console says API Key is required | `TARCSMEM_API_KEY` is enabled | Enter the same token in **集成中心 → 配置 API Key**; it stays in session storage |
| Console opens but shows no records | A new or different database was served | Run `tarcsmem seed --db <same-path> --if-empty`, then restart/refresh |
| `npm` rejects the engine | Node.js is older than 22 | Install Node.js 22 LTS and rerun `npm ci` |
| Gradio appears on port 7860 | The optional `tarcsmem ui` command was used | Use `tarcsmem serve` for the v0.8 FastAPI console |

The request `tenant_id` and `roles` fields are demo inputs, not authenticated identity. A
production gateway must inject verified OIDC/SSO claims. Never put real customer data or secrets
into this public smoke path.
