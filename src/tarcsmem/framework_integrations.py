"""One-line adapters for popular RAG frameworks.

Frameworks receive only the evidence that survived TARCS governance. They do
not get direct access to the underlying SQLite or vector candidate pool.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .models import AccessContext
from .service import TARCSMemoryService


def _governed_documents(
    service: TARCSMemoryService,
    query: str,
    as_of: date,
    access: AccessContext,
) -> list[dict[str, Any]]:
    result = service.query(query, as_of, access)
    return [
        {
            "text": item.record.fact,
            "score": item.tarcs_score,
            "metadata": {
                "id": item.record.id,
                "source_ref": item.record.source_ref,
                "status": item.record.status.value,
                "valid_from": (
                    item.record.valid_from.isoformat() if item.record.valid_from else None
                ),
                "valid_to": item.record.valid_to.isoformat() if item.record.valid_to else None,
                "classification": item.record.classification,
                "tarcs_score": round(item.tarcs_score, 6),
                "trace_id": result.trace_id,
            },
        }
        for item in result.selected
    ]


def as_langchain_retriever(
    service: TARCSMemoryService,
    as_of: date,
    access: AccessContext | None = None,
):
    """Return a LangChain ``BaseRetriever`` backed by GuardRead.

    Example: ``retriever = as_langchain_retriever(service, date.today())``.
    """
    try:
        from langchain_core.documents import Document
        from langchain_core.retrievers import BaseRetriever
        from pydantic import ConfigDict
    except ImportError as exc:  # pragma: no cover - minimal install path
        raise RuntimeError(
            "Install framework adapters: pip install 'tarcsmem[integrations]'"
        ) from exc

    resolved_access = access or AccessContext()

    class TARCSLangChainRetriever(BaseRetriever):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        service: Any
        business_date: date
        access_context: Any

        def _get_relevant_documents(self, query: str, *, run_manager=None):
            return [
                Document(page_content=item["text"], metadata=item["metadata"])
                for item in _governed_documents(
                    self.service,
                    query,
                    self.business_date,
                    self.access_context,
                )
            ]

    return TARCSLangChainRetriever(
        service=service,
        business_date=as_of,
        access_context=resolved_access,
    )


def as_llamaindex_retriever(
    service: TARCSMemoryService,
    as_of: date,
    access: AccessContext | None = None,
):
    """Return a LlamaIndex ``BaseRetriever`` backed by GuardRead.

    Example: ``retriever = as_llamaindex_retriever(service, date.today())``.
    """
    try:
        from llama_index.core.retrievers import BaseRetriever
        from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
    except ImportError as exc:  # pragma: no cover - minimal install path
        raise RuntimeError(
            "Install framework adapters: pip install 'tarcsmem[integrations]'"
        ) from exc

    resolved_access = access or AccessContext()

    class TARCSLlamaIndexRetriever(BaseRetriever):
        def __init__(self) -> None:
            self._service = service
            self._business_date = as_of
            self._access = resolved_access
            super().__init__()

        def _retrieve(self, query_bundle: QueryBundle):
            return [
                NodeWithScore(
                    node=TextNode(
                        id_=str(item["metadata"]["id"]),
                        text=str(item["text"]),
                        metadata=item["metadata"],
                    ),
                    score=float(item["score"]),
                )
                for item in _governed_documents(
                    self._service,
                    query_bundle.query_str,
                    self._business_date,
                    self._access,
                )
            ]

    return TARCSLlamaIndexRetriever()
