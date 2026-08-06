"""On-demand loaders for public, redistributable evaluation corpora.

The loader intentionally downloads only when a user asks for a sample in the
local UI. Raw benchmark files stay under ``data/external`` and are ignored by
Git; check the upstream licence before using any corpus beyond a portfolio PoC.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

FIQA_DATASET_CARD = "https://huggingface.co/datasets/BeIR/fiqa"
FIQA_ROWS_URL = "https://datasets-server.huggingface.co/rows"


@dataclass(frozen=True, slots=True)
class PublicDocument:
    document_id: str
    text: str
    title: str = ""


def _fiqa_path(data_dir: str | Path, limit: int) -> Path:
    return Path(data_dir) / "fiqa" / f"sample-{limit}.jsonl"


def download_fiqa_sample(
    limit: int = 100, data_dir: str | Path = "./data/external", timeout: int = 90
) -> Path:
    """Fetch and cache a bounded FiQA sample through Hugging Face's dataset API.

    This avoids downloading the whole corpus when a portfolio demo only needs a
    few hundred documents. It is an explicit UI/API action, never an import-time
    side effect.
    """
    if not 1 <= limit <= 2_000:
        raise ValueError("FiQA sample size must be between 1 and 2000 documents")
    target = _fiqa_path(data_dir, limit)
    if target.exists() and target.stat().st_size > 1024:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".part")
    # Some python.org macOS installations do not automatically point OpenSSL at
    # the system certificate store. Prefer certifi when it is available (it is
    # already installed with the UI stack), while retaining normal TLS checks.
    try:
        import certifi

        tls_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - platform-dependent fallback
        tls_context = ssl.create_default_context()
    try:
        with temporary.open("w", encoding="utf-8") as output:
            for offset in range(0, limit, 100):
                batch_size = min(100, limit - offset)
                query = f"?dataset=BeIR%2Ffiqa&config=corpus&split=corpus&offset={offset}&length={batch_size}"
                request = urllib.request.Request(
                    f"{FIQA_ROWS_URL}{query}",
                    headers={"User-Agent": "TARCS-Mem/0.7 public-dataset-loader"},
                )
                with urllib.request.urlopen(
                    request, timeout=timeout, context=tls_context
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                rows = payload.get("rows", [])
                if not rows:
                    break
                for row in rows:
                    json.dump(row.get("row", {}), output, ensure_ascii=False)
                    output.write("\n")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"无法下载 FiQA；请检查网络或稍后重试。来源：{FIQA_DATASET_CARD}"
        ) from exc
    if not temporary.exists() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("FiQA API 未返回可用的文档。")
    temporary.replace(target)
    return target


def load_fiqa_documents(
    limit: int = 100, data_dir: str | Path = "./data/external"
) -> list[PublicDocument]:
    """Read a bounded FiQA sample so a laptop never indexes the whole corpus by accident."""
    path = download_fiqa_sample(limit, data_dir)
    documents: list[PublicDocument] = []
    with path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            item = json.loads(raw_line)
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            documents.append(
                PublicDocument(
                    document_id=str(item.get("_id", len(documents))),
                    title=str(item.get("title", "")).strip(),
                    text=text,
                )
            )
            if len(documents) >= limit:
                break
    if not documents:
        raise RuntimeError("FiQA 下载完成，但未读取到可索引的文档。")
    return documents
