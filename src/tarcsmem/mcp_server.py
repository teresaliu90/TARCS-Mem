"""Model Context Protocol integration for governed enterprise memory.

The transport adapter is optional; the runtime stays dependency-light so its
security semantics can be tested without importing the MCP SDK.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from .models import AccessContext, MemoryRecord, SourceType
from .service import TARCSMemoryService

GOVERNANCE_RESOURCE = """# TARCS-Mem MCP governance contract

- Search applies tenant, role, memory-status, conflict and business-time controls before ranking.
- Tool arguments are demo caller attributes, not authenticated identity claims.
- `propose_memory` always writes a `user_claim`; it can enter review but cannot auto-activate.
- Model inference is never accepted as enterprise fact memory.
- Production hosts must derive tenant and roles from verified identity outside tool arguments.
"""


@dataclass(slots=True)
class MCPMemoryRuntime:
    """Framework-neutral implementation behind the MCP tools."""

    service: TARCSMemoryService

    @classmethod
    def from_path(cls, db_path: str) -> MCPMemoryRuntime:
        return cls(TARCSMemoryService(db_path))

    def search_trusted_memory(
        self,
        question: str,
        as_of: str,
        tenant_id: str = "default",
        roles: list[str] | None = None,
    ) -> dict[str, object]:
        """Return a governed evidence answer for one business date."""
        normalized = question.strip()
        if not normalized:
            raise ValueError("question cannot be empty")
        access = AccessContext.from_values(tenant_id, roles)
        return self.service.query(normalized, date.fromisoformat(as_of), access).to_dict()

    def propose_memory(
        self,
        fact: str,
        conflict_key: str,
        tenant_id: str = "default",
        classification: str = "internal",
        source_ref: str = "",
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> dict[str, object]:
        """Submit an untrusted claim to GuardWrite for human review.

        The source type and authority are intentionally fixed here. An LLM tool
        call cannot promote itself to an official policy or approved exception.
        """
        normalized_fact = fact.strip()
        normalized_key = conflict_key.strip()
        if not normalized_fact:
            raise ValueError("fact cannot be empty")
        if not normalized_key:
            raise ValueError("conflict_key cannot be empty")
        proposal_id = str(uuid4())
        reference = source_ref.strip() or f"MCP-PROPOSAL#{proposal_id}"
        record = MemoryRecord(
            id=proposal_id,
            fact=normalized_fact,
            source_type=SourceType.USER_CLAIM,
            source_ref=reference,
            authority=0.20,
            conflict_key=normalized_key,
            valid_from=valid_from,
            valid_to=valid_to,
            evidence=[reference],
            extraction_confidence=1.0,
            durable_value=0.8,
            tenant_id=tenant_id,
            classification=classification,
            metadata={"ingress": "mcp", "trust": "unverified_user_claim"},
        )
        admitted = self.service.ingest(record)
        return {
            "id": admitted.id,
            "status": admitted.status.value,
            "source_ref": admitted.source_ref,
            "message": "Proposal recorded; human review is required before activation.",
        }

    def close(self) -> None:
        self.service.close()


def create_mcp_server(db_path: str | None = None):
    """Create an official MCP Python SDK v2 server."""
    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise RuntimeError("Install MCP support: pip install 'tarcsmem[mcp]'") from exc

    runtime = MCPMemoryRuntime.from_path(
        db_path or os.getenv("TARCSMEM_DB_PATH", "./data/tarcsmem.db")
    )
    server = MCPServer(
        "TARCS-Mem",
        instructions=(
            "Search governed enterprise memory with business-time and access controls. "
            "Never present a memory proposal as approved policy."
        ),
    )

    @server.tool()
    def search_trusted_memory(
        question: str,
        as_of: str,
        tenant_id: str = "default",
        roles: list[str] | None = None,
    ) -> dict[str, object]:
        """Search only eligible enterprise memory at a YYYY-MM-DD business date."""
        return runtime.search_trusted_memory(question, as_of, tenant_id, roles)

    @server.tool()
    def propose_memory(
        fact: str,
        conflict_key: str,
        tenant_id: str = "default",
        classification: str = "internal",
        source_ref: str = "",
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> dict[str, object]:
        """Submit an untrusted claim for GuardWrite and mandatory human review."""
        return runtime.propose_memory(
            fact,
            conflict_key,
            tenant_id,
            classification,
            source_ref,
            valid_from,
            valid_to,
        )

    @server.resource("tarcsmem://governance")
    def governance_contract() -> str:
        """Describe the trust boundary applied to TARCS-Mem MCP tools."""
        return GOVERNANCE_RESOURCE

    # Keep the runtime reachable for in-process protocol tests and graceful
    # shutdown wrappers without making it part of the advertised MCP surface.
    server._tarcsmem_runtime = runtime  # type: ignore[attr-defined]
    return server


def main() -> None:
    """Run the MCP server over stdio for Codex, Claude Desktop and other hosts."""
    create_mcp_server().run()


if __name__ == "__main__":
    main()
