"""Local document parsing and chunking for the Agent ingestion path."""

from __future__ import annotations

from pathlib import Path


def parse_document(path: str | Path) -> str:
    """Return a document as Markdown-like text.

    Plain text and Markdown require no dependency. PDF, DOCX, PPTX and images
    use Docling when its optional extra is installed.
    """
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json", ".html", ".htm"}:
        return document_path.read_text(encoding="utf-8", errors="replace")
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError(
            "Install document support for PDF/DOCX/PPTX: pip install -e '.[documents]'"
        ) from exc
    result = DocumentConverter().convert(str(document_path))
    return result.document.export_to_markdown()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    """Create stable character chunks while preserving paragraph boundaries where possible."""
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            boundary = max(cleaned.rfind("。", start, end), cleaned.rfind("\n", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks
