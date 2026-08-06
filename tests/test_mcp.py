import asyncio
from datetime import date

import pytest

from tarcsmem.mcp_server import MCPMemoryRuntime, create_mcp_server
from tarcsmem.models import MemoryStatus
from tarcsmem.service import TARCSMemoryService


def test_mcp_search_uses_governed_business_time(tmp_path):
    service = TARCSMemoryService(tmp_path / "mcp-search.db")
    service.seed()
    runtime = MCPMemoryRuntime(service)

    result = runtime.search_trusted_memory(
        "华南区销售折扣上限是多少？",
        date(2026, 8, 15).isoformat(),
    )

    assert result["outcome"] == "answered"
    assert result["citations"] == ["POLICY-SALES-2026-07#1"]
    runtime.close()


def test_mcp_proposal_can_never_self_promote_to_active_policy(tmp_path):
    runtime = MCPMemoryRuntime.from_path(str(tmp_path / "mcp-proposal.db"))

    result = runtime.propose_memory(
        fact="模型建议将折扣上限改成30%。",
        conflict_key="sales_discount_limit:华南区",
        source_ref="AGENT-SUGGESTION#1",
    )

    assert result["status"] == "pending"
    stored = runtime.service.store.get(str(result["id"]))
    assert stored is not None
    assert stored.status is MemoryStatus.PENDING
    assert stored.authority == 0.20
    assert stored.source_type.value == "user_claim"
    runtime.close()


def test_mcp_runtime_rejects_invalid_dates_without_writing(tmp_path):
    runtime = MCPMemoryRuntime.from_path(str(tmp_path / "mcp-invalid.db"))
    with pytest.raises(ValueError):
        runtime.search_trusted_memory("制度是什么？", "not-a-date")
    assert runtime.service.store.count() == 0
    runtime.close()


def test_official_mcp_v2_server_exposes_expected_surface(tmp_path):
    mcp_sdk = pytest.importorskip("mcp")
    server = create_mcp_server(str(tmp_path / "mcp-protocol.db"))
    assert server.name == "TARCS-Mem"
    runtime = server._tarcsmem_runtime
    runtime.service.seed()

    async def exercise_protocol():
        async with mcp_sdk.Client(server) as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == {
                "search_trusted_memory",
                "propose_memory",
            }
            search = await client.call_tool(
                "search_trusted_memory",
                {
                    "question": "华南区销售折扣上限是多少？",
                    "as_of": "2026-08-15",
                },
            )
            assert search.is_error is False
            assert search.structured_content["citations"] == ["POLICY-SALES-2026-07#1"]
            proposal = await client.call_tool(
                "propose_memory",
                {
                    "fact": "MCP客户端建议将差旅上限改为9999元。",
                    "conflict_key": "travel_limit:深圳",
                },
            )
            assert proposal.is_error is False
            assert proposal.structured_content["status"] == "pending"
            resource = await client.read_resource("tarcsmem://governance")
            assert "cannot auto-activate" in resource.contents[0].text

    asyncio.run(exercise_protocol())
    runtime.close()
