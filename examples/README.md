# Integration examples

- `openai_compatible.py` calls the governed chat endpoint using only Python's
  standard library. Start `tarcsmem serve` first.
- `mcp-host-config.json` is a host-neutral MCP stdio configuration template.
  Replace both absolute paths before use.
- `typescript-client/` is a typed Node.js 22 smoke client for governed memory,
  business-date query, abstention handling, trace IDs, citations, and record audit history.

See `docs/INTEGRATIONS.md` for setup and security boundaries.
