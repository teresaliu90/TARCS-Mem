export type MemoryStatus =
  | "candidate"
  | "pending"
  | "verified_active"
  | "superseded"
  | "expired"
  | "rejected";

export type Memory = {
  id: string;
  fact: string;
  source_type: string;
  source_ref: string;
  authority: number;
  conflict_key: string;
  status: MemoryStatus;
  valid_from: string | null;
  valid_to: string | null;
  observed_at: string;
  evidence: string[];
  tenant_id: string;
  allowed_roles: string[];
  classification: string;
};

export type Overview = {
  version: string;
  total_memories: number;
  status_counts: Record<string, number>;
  classification_counts: Record<string, number>;
  review_queue: number;
  active_conflicts: number;
  expiring_soon: number;
  issues: Array<{
    id: string;
    kind: string;
    severity: string;
    title: string;
    source_ref: string;
    conflict_key: string;
  }>;
  privacy: string;
};

export type Integrations = {
  items: Array<{
    id: string;
    name: string;
    category: string;
    status: string;
    description: string;
    docs: string;
  }>;
  secrets_exposed: boolean;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = window.sessionStorage.getItem("tarcsmem_api_key");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (!response.ok)
    throw new Error(
      (await response.json().catch(() => null))?.detail ||
        `请求失败 (${response.status})`,
    );
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<Overview>("/v1/console/overview"),
  integrations: () => request<Integrations>("/v1/console/integrations"),
  memories: (params: URLSearchParams = new URLSearchParams()) =>
    request<{ items: Memory[]; total: number }>(`/v1/memories?${params}`),
  memory: (id: string) =>
    request<{
      memory: Memory;
      related_versions: Memory[];
      events: Array<{
        event_type: string;
        at: string;
        detail: Record<string, unknown>;
      }>;
    }>(`/v1/memories/${encodeURIComponent(id)}`),
  review: (
    id: string,
    decision: "approve" | "reject",
    reviewer: string,
    note: string,
  ) =>
    request<Memory>(`/v1/memories/${encodeURIComponent(id)}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer, note }),
      headers: { "Idempotency-Key": `console-${decision}-${id}-${Date.now()}` },
    }),
  query: (question: string, asOf: string) =>
    request<Record<string, unknown>>("/v1/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        as_of: asOf,
        tenant_id: "default",
        roles: [],
      }),
    }),
  observability: () => request<Record<string, unknown>>("/v1/observability"),
};
