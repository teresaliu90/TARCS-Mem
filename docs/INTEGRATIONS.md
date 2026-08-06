# Integration guide

TARCS-Mem exposes the same governance path through a native API, an
OpenAI-compatible facade and Model Context Protocol (MCP). These interfaces do
not bypass tenant, role, status, business-time, conflict, citation or cloud
egress controls.

## MCP v2 server

Install the official MCP Python SDK integration:

```bash
pip install -e '.[mcp]'
export TARCSMEM_DB_PATH=./data/tarcsmem.db
tarcsmem seed --db "$TARCSMEM_DB_PATH"
tarcsmem-mcp
```

`tarcsmem-mcp` uses stdio, so an MCP host should launch it as a child process.
A typical host configuration is:

```json
{
  "mcpServers": {
    "tarcsmem": {
      "command": "/absolute/path/to/venv/bin/tarcsmem-mcp",
      "env": {
        "TARCSMEM_DB_PATH": "/absolute/path/to/tarcsmem.db"
      }
    }
  }
}
```

The server exposes:

- `search_trusted_memory`: returns only evidence eligible for the requested
  tenant, roles and business date;
- `propose_memory`: records an untrusted `user_claim` with fixed low authority.
  It always requires human review and cannot impersonate an official policy;
- `tarcsmem://governance`: a resource describing the trust boundary for hosts
  and agents.

For protocol inspection, run the official MCP Inspector against the stdio
command. Production HTTP MCP deployments must add OAuth and derive tenant/role
claims from verified identity. Tool arguments are not an authentication system.

## OpenAI-compatible chat endpoint

Start TARCS-Mem with API and Agent dependencies:

```bash
pip install -e '.[api,agent,cloud]'
tarcsmem seed --db ./data/tarcsmem.db --if-empty
tarcsmem serve --db ./data/tarcsmem.db
```

Existing clients that accept an OpenAI-compatible base URL can use:

```text
base_url = http://127.0.0.1:8000/v1
model = tarcsmem-governed
```

Example request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model": "tarcsmem-governed",
    "messages": [{"role":"user","content":"2026年8月华南区折扣上限是多少？"}],
    "as_of": "2026-08-15",
    "stream": false
  }'
```

The standard `choices` and `usage` fields are present. An additive `tarcsmem`
field carries outcome, citations, decision trace and observability metadata.
Streaming is intentionally unsupported so the complete generated answer
can pass citation verification before any bytes cross the response boundary.

Client-supplied system messages are counted but ignored. Only the server-owned
governance prompt may define evidence, citation and egress policy. This prevents
an OpenAI-compatible caller from replacing GuardRead with an arbitrary system
instruction.

## Native endpoints

Use the native endpoints when you need complete typed governance data:

- `POST /v1/query` for deterministic governed retrieval;
- `POST /v1/chat` for governed retrieval plus generation;
- `POST /v1/memories` for GuardWrite ingestion;
- `POST /v1/memories/{id}/review` for named human decisions;
- `GET /v1/memories/{id}/audit` for append-only history.

The OpenAI and MCP surfaces are adapters over these controls, not separate
implementations.

## LangChain and LlamaIndex native retrievers

Install the optional framework dependencies:

```bash
pip install -e '.[integrations]'
```

Then create a native retriever with one function call:

```python
from datetime import date
from tarcsmem import TARCSMemoryService, as_langchain_retriever, as_llamaindex_retriever

service = TARCSMemoryService("./data/tarcsmem.db")
langchain_retriever = as_langchain_retriever(service, date.today())
llamaindex_retriever = as_llamaindex_retriever(service, date.today())
```

LangChain receives `Document` objects and LlamaIndex receives `NodeWithScore`
objects. Metadata includes the source reference, status, validity window,
classification, TARCS score and trace ID. The adapters deliberately call the
service-level governed query; they cannot access raw SQLite rows or the
pre-filter candidate pool.

## Confluence Cloud incremental sync

TARCS-Mem's first enterprise connector uses the Confluence Cloud REST API v2:

```bash
export TARCSMEM_CONFLUENCE_BASE_URL=https://your-site.atlassian.net
export TARCSMEM_CONFLUENCE_EMAIL=you@example.com
export TARCSMEM_CONFLUENCE_SPACE_ID=123456
export TARCSMEM_CONFLUENCE_API_TOKEN='read-from-your-secret-manager'

tarcsmem sync-confluence \
  --db ./data/tarcsmem.db \
  --checkpoint ./data/confluence-checkpoint.json \
  --tenant-id default \
  --classification internal \
  --role employee
```

The connector follows same-origin cursor links, fetches Confluence storage
format, converts it to plain text and writes deterministic page-version chunks
through GuardWrite. Its checkpoint contains only page IDs, version numbers,
content hashes and update timestamps—never tokens or page bodies. Unchanged
pages are not written again and a new version expires the older pending chunks.

Missing pages are reported but not deleted by default, because a permission
change can make a page disappear from an API response. Use `--expire-missing`
only in a controlled synchronization job after confirming the connector's
account still has complete space access. Imported pages default to
`meeting_note` with authority `0.70`, so they require human review. Use
`--source-type official_policy --authority 1.0` only when the source space has
an approved publication workflow.

This connector uses Basic authentication over verified TLS, as supported by
Confluence Cloud API tokens. Give the token read-only, least-privilege access,
store it in a secret manager and rotate it independently of the checkpoint.
