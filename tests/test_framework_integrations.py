from datetime import date

import pytest

from tarcsmem.framework_integrations import (
    _governed_documents,
    as_langchain_retriever,
    as_llamaindex_retriever,
)
from tarcsmem.models import AccessContext
from tarcsmem.service import TARCSMemoryService


def seeded_service(tmp_path):
    service = TARCSMemoryService(tmp_path / "frameworks.db")
    service.seed()
    return service


def test_framework_projection_contains_only_governed_evidence(tmp_path):
    service = seeded_service(tmp_path)
    documents = _governed_documents(
        service,
        "2026年8月华南区销售折扣上限是多少？",
        date(2026, 8, 15),
        AccessContext(),
    )
    assert len(documents) == 1
    assert documents[0]["metadata"]["source_ref"] == "POLICY-SALES-2026-07#1"
    assert documents[0]["metadata"]["trace_id"]
    assert documents[0]["score"] > 0
    service.close()


def test_langchain_one_line_adapter_invokes_real_retriever(tmp_path):
    pytest.importorskip("langchain_core")
    service = seeded_service(tmp_path)
    retriever = as_langchain_retriever(service, date(2026, 8, 15))
    documents = retriever.invoke("华南区销售折扣上限是多少？")
    assert [item.metadata["source_ref"] for item in documents] == ["POLICY-SALES-2026-07#1"]
    service.close()


def test_llamaindex_one_line_adapter_invokes_real_retriever(tmp_path):
    pytest.importorskip("llama_index.core")
    service = seeded_service(tmp_path)
    retriever = as_llamaindex_retriever(service, date(2026, 8, 15))
    nodes = retriever.retrieve("华南区销售折扣上限是多少？")
    assert [item.metadata["source_ref"] for item in nodes] == ["POLICY-SALES-2026-07#1"]
    service.close()
