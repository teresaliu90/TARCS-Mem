import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  ApiError,
  type FetchLike,
  TarcsMemClient,
} from "./typescript_api_client.ts";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("the TypeScript client follows the governed /v1 API flow", async () => {
  const calls: Array<{ url: string; method: string }> = [];
  const fetchImpl: FetchLike = async (input, init) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? "GET" });
    if (url.endsWith("/memories")) {
      return jsonResponse({
        id: "synthetic-example",
        status: "verified_active",
        source_ref: "synthetic/typescript-example.md#1",
        fact: "Synthetic fact",
      });
    }
    if (url.endsWith("/query")) {
      return jsonResponse({
        outcome: "answered",
        answer: "Based on governed evidence",
        citations: ["synthetic/typescript-example.md#1"],
        observability: { trace_id: "trace-001" },
      });
    }
    if (url.endsWith("/audit")) {
      return jsonResponse({ record_id: "synthetic-example", events: [] });
    }
    return jsonResponse({ detail: "unexpected path" }, 404);
  };

  const client = new TarcsMemClient(
    "https://example.test/v1",
    "test-token",
    fetchImpl,
  );
  const record = await client.createMemory({
    fact: "Synthetic fact",
    source_type: "official_policy",
    source_ref: "synthetic/typescript-example.md#1",
    authority: 1,
    conflict_key: "synthetic-example",
    evidence: ["synthetic/typescript-example.md#1"],
  });
  const result = await client.query("What is the fact?", "2026-08-15");
  const audit = await client.audit(record.id);

  assert.equal(result.outcome, "answered");
  assert.deepEqual(result.citations, ["synthetic/typescript-example.md#1"]);
  assert.equal(result.observability?.trace_id, "trace-001");
  assert.equal(audit.record_id, record.id);
  assert.deepEqual(calls, [
    { url: "https://example.test/v1/memories", method: "POST" },
    { url: "https://example.test/v1/query", method: "POST" },
    {
      url: "https://example.test/v1/memories/synthetic-example/audit",
      method: "GET",
    },
  ]);
});

test("API failures are surfaced as typed errors", async () => {
  const fetchImpl: FetchLike = async () =>
    jsonResponse({ detail: "valid bearer token required" }, 401);
  const client = new TarcsMemClient(
    "https://example.test/v1",
    undefined,
    fetchImpl,
  );

  await assert.rejects(
    client.query("What is unavailable?", "2026-08-15"),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 401 &&
      error.detail === "valid bearer token required",
  );
});
