/**
 * Minimal typed TARCS-Mem v0.8 API client.
 *
 * Governance decisions remain server-owned. This client supplies only the
 * business question, business date, and demo identity inputs; it never marks a
 * memory authoritative or overrides admission, conflict, or retrieval policy.
 */

declare const process: {
  env: Record<string, string | undefined>;
  exitCode?: number;
};

type QueryOutcome = "answered" | "abstained";

interface MemoryReference {
  id: string;
  source_ref: string;
  status: string;
  tenant_id: string;
}

interface MemoryDetailResponse {
  memory: MemoryReference;
}

interface RecordAuditResponse {
  record_id: string;
  events: Array<{
    id: string;
    event_type: string;
    at: string;
  }>;
}

interface QueryResponse {
  answer_id: string;
  evidence_pack_id: string;
  outcome: QueryOutcome;
  answer: string;
  citations: string[];
  observability: {
    trace_id: string | null;
  };
}

class ApiHttpError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(status: number, requestId: string | null) {
    super(`TARCS-Mem API returned HTTP ${status}`);
    this.name = "ApiHttpError";
    this.status = status;
    this.requestId = requestId;
  }
}

const baseUrl = (
  process.env.TARCSMEM_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");
const apiKey = process.env.TARCSMEM_API_KEY?.trim();
const tenantId = process.env.TARCSMEM_TENANT_ID?.trim() || "default";
const memoryId = process.env.TARCSMEM_MEMORY_ID?.trim() || "sales-v2";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (apiKey) headers.set("Authorization", `Bearer ${apiKey}`);

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    // Do not echo response bodies: production gateways may attach sensitive detail.
    throw new ApiHttpError(response.status, response.headers.get("x-request-id"));
  }
  return (await response.json()) as T;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`API contract check failed: ${field} is missing`);
  }
  return value;
}

async function main(): Promise<void> {
  const scope = new URLSearchParams({ tenant_id: tenantId });
  const detail = await request<MemoryDetailResponse>(
    `/v1/memories/${encodeURIComponent(memoryId)}?${scope}`,
  );
  requireString(detail.memory.source_ref, "memory.source_ref");
  console.log(
    "governed_memory:",
    JSON.stringify({
      id: detail.memory.id,
      status: detail.memory.status,
      source_ref: detail.memory.source_ref,
    }),
  );

  const history = await request<RecordAuditResponse>(
    `/v1/memories/${encodeURIComponent(memoryId)}/audit?${scope}`,
  );
  if (!Array.isArray(history.events) || history.events.length === 0) {
    throw new Error("API contract check failed: record audit history is empty");
  }
  console.log(
    "record_audit:",
    JSON.stringify({
      record_id: history.record_id,
      events: history.events.map((event) => event.event_type),
    }),
  );

  const result = await request<QueryResponse>("/v1/query", {
    method: "POST",
    body: JSON.stringify({
      question: "2026年8月华南区销售折扣上限是多少？",
      as_of: "2026-08-15",
      tenant_id: tenantId,
      roles: [],
    }),
  });
  requireString(result.answer_id, "answer_id");
  requireString(result.evidence_pack_id, "evidence_pack_id");
  console.log(
    "query_result:",
    JSON.stringify({
      outcome: result.outcome,
      citations: result.citations,
      trace_id: result.observability.trace_id,
      answer_id: result.answer_id,
    }),
  );

  if (result.outcome === "abstained") {
    console.log("abstention: no eligible governed evidence; no answer was assumed");
    return;
  }
  if (result.outcome !== "answered") {
    throw new Error(`API contract check failed: unsupported outcome ${String(result.outcome)}`);
  }
  if (result.citations.length === 0) {
    throw new Error("API contract check failed: answered result has no citation");
  }
}

if (process.env.TARCSMEM_CONTRACT_ONLY !== "1") {
  main().catch((error: unknown) => {
    if (error instanceof ApiHttpError) {
      const hint =
        error.status === 401
          ? "Set TARCSMEM_API_KEY to the server token."
          : "Check that the seeded FastAPI service is running.";
      console.error(
        `${error.message}; request_id=${error.requestId ?? "unavailable"}. ${hint}`,
      );
    } else {
      console.error(error instanceof Error ? error.message : "Unknown client error");
    }
    process.exitCode = 1;
  });
}
