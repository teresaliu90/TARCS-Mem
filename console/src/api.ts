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

export type QueryResponse = {
  answer_id?: string;
  evidence_pack_id?: string;
  correlation_id?: string;
  outcome: string;
  answer: string;
  citations?: string[];
  selected_evidence?: Array<Record<string, unknown>>;
  decision_trace?: Record<string, unknown>;
  observability?: Record<string, unknown>;
};

export type AnswerAuditTrail = {
  answer_id: string;
  evidence_pack_id: string;
  correlation_id: string;
  outcome: string;
  created_at: string;
  as_of: string;
  query_hash: string;
  principal_snapshot_hash: string;
  selected_evidence: Array<{
    memory_id: string;
    source_ref: string;
    classification: string;
    valid_from: string | null;
    valid_to: string | null;
    selected_reason_codes: string[];
    scores: Record<string, number>;
    write_event_ids: string[];
    approval_event_ids: string[];
    supersedes_memory_id: string | null;
  }>;
  excluded_summary: Record<string, number>;
  policy_versions: Record<
    string,
    { policy_id: string; version: string; digest: string }
  >;
  verification: Record<string, string>;
  integrity: Record<string, unknown>;
  trace_id: string | null;
};

export type ApiErrorCode =
  | "network"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "invalid"
  | "rate_limited"
  | "unavailable"
  | "request_failed";

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function safeHttpError(status: number): ApiError {
  if (status === 401)
    return new ApiError("unauthorized", "需要配置有效的 API Key 后才能继续。");
  if (status === 403)
    return new ApiError("forbidden", "当前身份没有执行此操作的权限。");
  if (status === 404)
    return new ApiError("not_found", "记录不存在，或当前身份无权访问。");
  if (status === 409)
    return new ApiError("conflict", "治理状态已发生变化，请刷新后重试。");
  if (status === 422)
    return new ApiError("invalid", "输入未通过校验，请检查后重试。");
  if (status === 429)
    return new ApiError("rate_limited", "请求过于频繁，请稍后重试。");
  if (status >= 500)
    return new ApiError("unavailable", "治理服务暂时不可用，请稍后重新连接。");
  return new ApiError("request_failed", `请求失败（HTTP ${status}）。`);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = window.sessionStorage.getItem("tarcsmem_api_key");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch {
    throw new ApiError("network", "无法连接治理服务，请确认服务已启动。");
  }
  if (!response.ok) throw safeHttpError(response.status);
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("request_failed", "服务返回无法读取，请刷新后重试。");
  }
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
    request<QueryResponse>("/v1/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        as_of: asOf,
        tenant_id: "default",
        roles: [],
      }),
    }),
  answerAudit: (answerId: string) =>
    request<AnswerAuditTrail>(
      `/v1/answers/${encodeURIComponent(answerId)}/audit`,
    ),
  observability: () => request<Record<string, unknown>>("/v1/observability"),
};
