# Run the full local Agent

This guide runs a complete local stack. The software and open-weight models can be used without a paid inference API, but model downloads, disk space, RAM and electricity are still required.

## 1. Install services

Install [Ollama](https://ollama.com/), then start the local LLM:

```bash
ollama pull qwen3:4b
ollama serve
```

For a stronger machine, change the model tag to `qwen3:8b`. The repository's zero-config profile is an extractive demo, not an LLM; this guide explicitly enables Qwen3 through `TARCSMEM_OLLAMA_MODEL`.

## 2. Install application extras

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[api,ui,local-models,documents,dev]'
```

The default vector database is embedded Qdrant local mode at `./data/qdrant`, so Docker is not required. Enable the full local model path explicitly; the first BGE call downloads its model weights:

```bash
export TARCSMEM_LLM_PROVIDER=ollama
export TARCSMEM_EMBEDDING_BACKEND=bge
export TARCSMEM_BGE_MODEL=BAAI/bge-m3
export TARCSMEM_RERANKER=bge
export TARCSMEM_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

For the dependency-free preview instead, keep `TARCSMEM_LLM_PROVIDER=extractive`, `TARCSMEM_EMBEDDING_BACKEND=hash` and `TARCSMEM_RERANKER=off`.

## 3. Launch

```bash
tarcsmem ui --db ./data/tarcsmem.db
```

Open the local address printed by Gradio, normally `http://127.0.0.1:7860`.

The three tabs are:

- **对话与证据**: cited multi-turn Q&A and TARCS decision details;
- **知识接入**: local document upload plus a public SEC EDGAR connector;
- **记忆治理与审计**: approve/reject pending records with a named reviewer and note, then inspect the append-only audit trail.

## Real public-data PoC

The SEC EDGAR connector requests public company facts by CIK. Enter a descriptive `User-Agent` with a contact email as required by SEC access guidance. It is a real public-data proof of integration, not a customer deployment. Never upload confidential material without authorization.

## Container option

Run Qdrant separately with `docker compose up qdrant -d`; run Ollama on the host so downloaded model weights persist outside the app container. For Linux Docker, point `TARCSMEM_OLLAMA_URL` to the host gateway; on Docker Desktop use `http://host.docker.internal:11434`.

## Security boundary

The UI is designed for local demonstration. Do not expose it publicly before adding SSO, RBAC, document ACL filters, tenant isolation, secrets management, malware scanning, rate limiting, logging redaction and human approval workflows.
