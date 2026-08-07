/**
 * Small, dependency-free TypeScript client for TARCS-Mem's versioned /v1 API.
 *
 * The request types intentionally omit status and other governance decisions:
 * admission and policy remain server-owned.
 */

declare const process: {
  argv: string[];
  env: Record<string, string | undefined>;
  exitCode?: number;
};

export type SourceType =
  | "official_policy"
  | "approved_exception"
  | "system_record"
  | "public_dataset"
  | "meeting_note"
  | "user_claim";

export interface GovernedMemoryInput {
  fact: string;
  source_type: SourceType;
  source_ref: string;
  authority: number;
  conflict_key: string;
  valid_from?: string;
  valid_to?: string;
  evidence: string[];
  tenant_id?: string;
  allowed_roles?: string[];
  classification?: "public" | "internal" | "confidential" | "restricted";
}

export interface GovernedMemory {
  id: string;
  status: string;
  source_ref: string;
  fact: string;
  [key: string]: unknown;
}

export interface QueryResponse {
  outcome: "answered" | "abstained";
  answer: string;
  citations: string[];
  observability?: {
    trace_id?: string | null;
    latency_ms?: number | null;
  };
  [key: string]: unknown;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  record_id: string;
  at: string;
  detail: Record<string, unknown>;
}

export interface AuditResponse {
  record_id: string;
  events: AuditEvent[];
}

export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(`TARCS-Mem API request failed (${status}): ${String(detail)}`);
    this.name = "ApiError";
  }
}

export class TarcsMemClient {
  private readonly baseUrl: string;
  private readonly apiKey: string | undefined;
  private readonly fetchImpl: FetchLike;

  constructor(
    baseUrl = process.env.TARCSMEM_BASE_URL ?? "http://127.0.0.1:8000/v1",
    apiKey = process.env.TARCSMEM_API_KEY,
    fetchImpl: FetchLike = fetch,
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.fetchImpl = fetchImpl;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("accept", "application/json");
    if (init.body !== undefined) headers.set("content-type", "application/json");
    if (this.apiKey) headers.set("authorization", `Bearer ${this.apiKey}`);

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    const text = await response.text();
    let payload: unknown = undefined;
    if (text) {
      try {
        payload = JSON.parse(text) as unknown;
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? payload.detail
          : payload;
      throw new ApiError(response.status, detail);
    }
    return payload as T;
  }

  createMemory(record: GovernedMemoryInput): Promise<GovernedMemory> {
    return this.request<GovernedMemory>("/memories", {
      method: "POST",
      body: JSON.stringify({ record }),
    });
  }

  query(
    question: string,
    asOf: string,
    tenantId = "default",
    roles: string[] = [],
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        as_of: asOf,
        tenant_id: tenantId,
        roles,
      }),
    });
  }

  audit(recordId: string): Promise<AuditResponse> {
    return this.request<AuditResponse>(
      `/memories/${encodeURIComponent(recordId)}/audit`,
    );
  }
}

export function printQuery(result: QueryResponse): void {
  console.log(`Outcome: ${result.outcome}`);
  if (result.outcome === "abstained") {
    console.log(`Abstained: ${result.answer}`);
    console.log("Citations: none");
  } else {
    console.log(`Answer: ${result.answer}`);
    console.log(`Citations: ${result.citations.join(", ") || "none"}`);
  }
  console.log(`Trace ID: ${result.observability?.trace_id ?? "unavailable"}`);
}

async function main(): Promise<void> {
  const client = new TarcsMemClient();
  const record = await client.createMemory({
    fact: "Synthetic support refunds up to $500 may be approved by the support team from 2026-08-01.",
    source_type: "official_policy",
    source_ref: "synthetic/typescript-example.md#1",
    authority: 1,
    conflict_key: "typescript-example:support-refund-limit",
    valid_from: "2026-08-01",
    evidence: ["synthetic/typescript-example.md#1"],
  });
  console.log(`Created governed memory ${record.id} with server status ${record.status}.`);

  const result = await client.query(
    "What is the synthetic support refund approval limit?",
    "2026-08-15",
  );
  printQuery(result);

  const audit = await client.audit(record.id);
  console.log(`Audit events: ${audit.events.length}`);
}

const isMainModule = process.argv[1]?.endsWith("typescript_api_client.ts") ?? false;
if (isMainModule) {
  main().catch((error: unknown) => {
    if (error instanceof ApiError) {
      console.error(`API error ${error.status}: ${String(error.detail)}`);
    } else {
      console.error(error);
    }
    process.exitCode = 1;
  });
}
