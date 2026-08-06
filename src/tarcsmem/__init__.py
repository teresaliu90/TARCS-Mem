"""TARCS-Mem: trusted enterprise memory governance."""

from .framework_integrations import as_langchain_retriever, as_llamaindex_retriever
from .service import TARCSMemoryService

__version__ = "0.7.0"

__all__ = [
    "TARCSMemoryService",
    "__version__",
    "as_langchain_retriever",
    "as_llamaindex_retriever",
]
