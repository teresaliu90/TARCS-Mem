import { readFile } from "node:fs/promises";

const source = await readFile(
  new URL("../examples/typescript_api_client.ts", import.meta.url),
  "utf8",
);
const inputStart = source.indexOf("export interface GovernedMemoryInput");
const inputEnd = source.indexOf("export interface GovernedMemory {", inputStart);
const inputContract = source.slice(inputStart, inputEnd);

const checks = [
  ["typed governed-memory input", inputStart >= 0],
  ["server-owned status", !/\bstatus\b/.test(inputContract)],
  ["versioned base URL", source.includes("http://127.0.0.1:8000/v1")],
  ["memory creation route", source.includes('"/memories"')],
  ["query route", source.includes('"/query"')],
  ["audit route", source.includes("/audit")],
  ["abstention branch", source.includes('result.outcome === "abstained"')],
  ["citations output", source.includes("result.citations")],
  ["trace output", source.includes("trace_id")],
  ["typed API error", source.includes("class ApiError")],
  ["secret environment variable", source.includes("TARCSMEM_API_KEY")],
];

const failures = checks.filter(([, passed]) => !passed).map(([name]) => name);
if (failures.length > 0) {
  console.error(`TypeScript example smoke check failed: ${failures.join(", ")}`);
  process.exit(1);
}

console.log(`TypeScript example smoke check passed (${checks.length} checks).`);
