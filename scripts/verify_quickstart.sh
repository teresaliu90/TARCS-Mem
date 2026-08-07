#!/usr/bin/env bash
set -euo pipefail

smoke_port="${TARCSMEM_SMOKE_PORT:-8765}"
tarcsmem_bin="${TARCSMEM_BIN:-tarcsmem}"
smoke_dir="$(mktemp -d "${TMPDIR:-/tmp}/tarcsmem-quickstart.XXXXXX")"
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  case "${smoke_dir}" in
    */tarcsmem-quickstart.*) rm -rf -- "${smoke_dir}" ;;
  esac
}
trap cleanup EXIT

if ! command -v "${tarcsmem_bin}" >/dev/null 2>&1; then
  echo "ERROR: tarcsmem is not installed. Run: pip install -e '.[api]'" >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for the reproducible HTTP smoke check." >&2
  exit 1
fi

python - "${smoke_port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as sock:
    if sock.connect_ex(("127.0.0.1", port)) == 0:
        raise SystemExit(f"ERROR: port {port} is already in use; set TARCSMEM_SMOKE_PORT")
PY

database="${smoke_dir}/synthetic-demo.db"
base_url="http://127.0.0.1:${smoke_port}"

echo "[1/5] Seed six synthetic governance records"
"${tarcsmem_bin}" seed --db "${database}" --if-empty

echo "[2/5] Start the FastAPI console without an API key or model provider"
TARCSMEM_API_KEY= "${tarcsmem_bin}" serve \
  --db "${database}" --host 127.0.0.1 --port "${smoke_port}" \
  >"${smoke_dir}/server.log" 2>&1 &
server_pid="$!"

ready=""
for _ in {1..50}; do
  if curl -fsS "${base_url}/healthz" >"${smoke_dir}/health.json" 2>/dev/null; then
    ready="yes"
    break
  fi
  sleep 0.1
done
if [[ -z "${ready}" ]]; then
  echo "ERROR: API did not become ready. Safe server log follows:" >&2
  tail -20 "${smoke_dir}/server.log" >&2
  exit 1
fi

echo "[3/5] Verify /console/ and the Policy version query"
curl -fsS "${base_url}/console/" >"${smoke_dir}/console.html"
grep -q "TARCS-Mem" "${smoke_dir}/console.html"
curl -fsS -X POST "${base_url}/v1/query" \
  -H 'content-type: application/json' \
  -d '{"question":"2026年8月华南区销售折扣上限是多少？","as_of":"2026-08-15","tenant_id":"default","roles":[]}' \
  >"${smoke_dir}/query.json"

answer_id="$(python - "${smoke_dir}/query.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["outcome"] == "answered", payload
assert payload["citations"] == ["POLICY-SALES-2026-07#1"], payload
assert payload["selected_evidence"][0]["id"] == "sales-v2", payload
assert "sales-meeting-note" not in json.dumps(payload["selected_evidence"]), payload
assert payload["observability"]["trace_id"], payload
print(payload["answer_id"])
PY
)"

echo "[4/5] Verify the answer evidence chain and synthetic record history"
curl -fsS "${base_url}/v1/answers/${answer_id}/audit" >"${smoke_dir}/answer-audit.json"
curl -fsS "${base_url}/v1/memories/sales-v2/audit" >"${smoke_dir}/record-audit.json"
python - "${smoke_dir}/answer-audit.json" "${smoke_dir}/record-audit.json" <<'PY'
import json
import sys

answer = json.load(open(sys.argv[1], encoding="utf-8"))
record = json.load(open(sys.argv[2], encoding="utf-8"))
assert answer["selected_evidence"][0]["memory_id"] == "sales-v2", answer
assert answer["integrity"] == {
    "chain_verified": False,
    "mode": "sqlite_reference_store",
}, answer
assert record["record_id"] == "sales-v2" and record["events"], record
PY

echo "[5/5] Critical Quickstart path passed"
if [[ "${TARCSMEM_RUN_TYPESCRIPT_SMOKE:-0}" == "1" ]]; then
  echo "[extra] Run the Node.js 22 TypeScript client against the same API"
  TARCSMEM_BASE_URL="${base_url}" npm --prefix examples/typescript-client run smoke
fi

echo "PASS: console, governed answer, citation, trace, and both audit paths use synthetic data only."
