"""Optional local adapters for Ollama, BGE models and Qdrant.

The core TARCS algorithm has no model/vendor dependency. These adapters make
the repository a complete local Agent when optional extras are installed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from .retrieval import tokens


class EmbeddingModel(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def rerank(self, query: str, passages: list[str]) -> list[float]: ...


class LLMClient(Protocol):
    """Minimal generation interface shared by local and cloud providers."""

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str: ...


@dataclass(slots=True)
class HashEmbedding:
    """Dependency-free deterministic fallback for CI and development only."""

    dimension: int = 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in tokens(text):
                index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dimension
                vector[index] += 1.0
            magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / magnitude for value in vector])
        return vectors


class BGEEmbedding:
    """BGE adapter with a laptop-safe default and optional BGE-M3 upgrade."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        try:
            from FlagEmbedding import BGEM3FlagModel, FlagModel
        except ImportError as exc:
            raise RuntimeError("Install local models: pip install -e '.[local-models]'") from exc
        self.model_name = model_name
        self.is_m3 = model_name == "BAAI/bge-m3"
        self.model = (
            BGEM3FlagModel(model_name, use_fp16=False)
            if self.is_m3
            else FlagModel(model_name, use_fp16=False)
        )
        probe = self.embed(["dimension probe"])[0]
        self.dimension = len(probe)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.is_m3:
            result = self.model.encode(texts, batch_size=8, max_length=8192)
            vectors = result["dense_vecs"]
        else:
            vectors = self.model.encode(texts, batch_size=16, max_length=512)
        return [list(map(float, vector)) for vector in vectors]


class BGEReranker:
    """Cross-encoder reranker used only after vector candidate retrieval."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError("Install local models: pip install -e '.[local-models]'") from exc
        self.model = FlagReranker(model_name, use_fp16=False)

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        scores = self.model.compute_score([[query, item] for item in passages], normalize=True)
        return [float(score) for score in scores]


class ExtractiveDemoClient:
    """Zero-credential renderer for the reproducible first-run experience.

    It is not an LLM and performs no reasoning. It renders the already governed
    evidence blocks with exact source labels so users can exercise the complete
    write/retrieve/audit/UI path before configuring Ollama or a cloud provider.
    """

    provider_name = "Extractive Demo（本地、非大模型）"
    model = "deterministic-evidence-renderer"
    is_cloud = False
    _evidence_block = re.compile(
        r"\[SOURCE:\s*(?P<source>[^\]\r\n]+)\]\n"
        r"\[VALID_FROM:[^\r\n]+\]\n"
        r"\[VALID_TO:[^\r\n]+\]\n"
        r"\[AUTHORITY:[^\r\n]+\]\n"
        r"(?P<fact>.*?)(?=\n\n\[SOURCE:|\Z)",
        re.DOTALL,
    )

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        return str(self.chat_with_metrics(messages, temperature)["content"])

    def chat_with_metrics(
        self, messages: list[dict[str, str]], temperature: float = 0.1
    ) -> dict[str, int | float | str | None]:
        del temperature
        system = next(
            (message.get("content", "") for message in messages if message.get("role") == "system"),
            "",
        )
        blocks = [
            (match.group("source").strip(), match.group("fact").strip())
            for match in self._evidence_block.finditer(system)
        ]
        if not blocks:
            raise RuntimeError("Extractive demo received no governed evidence blocks.")
        content = "基于受治理证据：\n" + "\n".join(
            f"- {fact} [SOURCE: {source}]" for source, fact in blocks[:3]
        )
        return {
            "content": content,
            "provider": "extractive-demo",
            "model": self.model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_duration_ms": 0.0,
        }


class OllamaClient:
    provider_name = "Ollama（本地）"
    is_cloud = False

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:4b") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.base_url}. Start Ollama and pull {self.model}."
            ) from exc

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        return self.chat_with_metrics(messages, temperature)["content"]

    def chat_with_metrics(
        self, messages: list[dict[str, str]], temperature: float = 0.1
    ) -> dict[str, int | str | None]:
        result = self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        return {
            "content": str(result["message"]["content"]).strip(),
            "provider": "ollama",
            "model": str(result.get("model", self.model)),
            "prompt_tokens": int(result.get("prompt_eval_count", 0) or 0),
            "completion_tokens": int(result.get("eval_count", 0) or 0),
            "total_duration_ms": round(int(result.get("total_duration", 0) or 0) / 1_000_000, 1),
            "load_duration_ms": round(int(result.get("load_duration", 0) or 0) / 1_000_000, 1),
            "eval_duration_ms": round(int(result.get("eval_duration", 0) or 0) / 1_000_000, 1),
        }


class DeepSeekClient:
    """Dependency-free client for DeepSeek's OpenAI-compatible Chat API.

    The API key is kept only in process memory and is never included in errors,
    metrics or request payloads. RAG answers default to non-thinking mode to
    control latency and cost; callers can opt into thinking through environment
    configuration.
    """

    provider_name = "DeepSeek API（云端）"
    is_cloud = True
    retryable_statuses: ClassVar[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout: float = 90.0,
        max_retries: int = 2,
        max_tokens: int = 1024,
        thinking: bool = False,
    ) -> None:
        if not api_key.strip():
            raise RuntimeError(
                "DeepSeek provider requires DEEPSEEK_API_KEY. "
                "Set it in your terminal or an untracked .env file."
            )
        normalized_url = base_url.rstrip("/")
        if not normalized_url.startswith("https://"):
            raise ValueError("DeepSeek base URL must use HTTPS")
        if model not in {"deepseek-v4-flash", "deepseek-v4-pro"}:
            raise ValueError("DeepSeek model must be deepseek-v4-flash or deepseek-v4-pro")
        if timeout <= 0 or max_retries < 0 or max_tokens <= 0:
            raise ValueError("DeepSeek timeout, retries and max tokens must be positive")
        self._api_key = api_key
        self.base_url = normalized_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self.thinking = thinking
        ca_bundle = os.getenv("TARCSMEM_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
        if not ca_bundle:
            try:
                import certifi
            except ImportError:
                certifi = None  # type: ignore[assignment]
            if certifi is not None:
                ca_bundle = certifi.where()
        self._ssl_context = ssl.create_default_context(cafile=ca_bundle or None)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "TARCS-Mem/0.7",
            },
            method="POST",
        )
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                    context=self._ssl_context,
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in self.retryable_statuses and attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                if exc.code in {401, 403}:
                    raise RuntimeError(
                        "DeepSeek API authentication failed. Rotate the key and check DEEPSEEK_API_KEY."
                    ) from None
                if exc.code == 402:
                    raise RuntimeError("DeepSeek API balance is insufficient.") from None
                if exc.code == 429:
                    raise RuntimeError("DeepSeek API rate limit exceeded; retry later.") from None
                raise RuntimeError(f"DeepSeek API request failed with HTTP {exc.code}.") from None
            except urllib.error.URLError:
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise RuntimeError(
                    "Cannot reach the DeepSeek API. Check network and base URL."
                ) from None
        raise RuntimeError("DeepSeek API request failed after retries.")  # pragma: no cover

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        return str(self.chat_with_metrics(messages, temperature)["content"])

    def chat_with_metrics(
        self, messages: list[dict[str, str]], temperature: float = 0.1
    ) -> dict[str, int | float | str | None]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if self.thinking:
            payload["reasoning_effort"] = "high"
        started = time.perf_counter()
        result = self._post(payload)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("DeepSeek API returned no completion choice.")
        choice = choices[0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("DeepSeek API returned an empty answer.")
        usage = result.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        details = usage.get("completion_tokens_details", {})
        if not isinstance(details, dict):
            details = {}
        return {
            "content": content.strip(),
            "provider": "deepseek",
            "model": str(result.get("model", self.model)),
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
            "prompt_cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens", 0) or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens", 0) or 0),
            "finish_reason": str(choice.get("finish_reason", "")),
            "total_duration_ms": latency_ms,
        }


class QdrantVectorStore:
    """Small REST client: no Qdrant Python SDK is required for the demo."""

    def __init__(
        self,
        base_url: str = "local://./data/qdrant",
        collection: str = "tarcsmem_evidence",
        dimension: int = 1024,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.dimension = dimension
        self._local = None
        if base_url.startswith("local://"):
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise RuntimeError("Install Qdrant local mode: pip install qdrant-client") from exc
            local_path = base_url.removeprefix("local://") or "./data/qdrant"
            self._local = QdrantClient(path=local_path)

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        )
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach Qdrant at {self.base_url}. Start the Qdrant service."
            ) from exc

    def ensure_collection(self) -> None:
        if self._local is not None:
            from qdrant_client.models import Distance, VectorParams

            if not self._local.collection_exists(self.collection):
                self._local.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
            return
        try:
            self._request("GET", f"/collections/{self.collection}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            self._request(
                "PUT",
                f"/collections/{self.collection}",
                {"vectors": {"size": self.dimension, "distance": "Cosine"}},
            )

    @staticmethod
    def _point_id(record_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tarcsmem:{record_id}"))

    def upsert(self, entries: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        self.ensure_collection()
        if self._local is not None:
            from qdrant_client.models import PointStruct

            points = [
                PointStruct(
                    id=self._point_id(record_id),
                    vector=vector,
                    payload={"record_id": record_id, **payload},
                )
                for record_id, vector, payload in entries
            ]
            if points:
                self._local.upsert(collection_name=self.collection, points=points, wait=True)
            return
        points = [
            {
                "id": self._point_id(record_id),
                "vector": vector,
                "payload": {"record_id": record_id, **payload},
            }
            for record_id, vector, payload in entries
        ]
        if points:
            self._request(
                "PUT", f"/collections/{self.collection}/points?wait=true", {"points": points}
            )

    def search(
        self,
        vector: list[float],
        limit: int = 12,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        if self._local is not None:
            query_filter = None
            if tenant_id:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                query_filter = Filter(
                    must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
                )
            result = self._local.query_points(
                collection_name=self.collection,
                query=vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return [{"payload": item.payload or {}, "score": item.score} for item in result.points]
        query_filter = None
        if tenant_id:
            query_filter = {"must": [{"key": "tenant_id", "match": {"value": tenant_id}}]}
        result = self._request(
            "POST",
            f"/collections/{self.collection}/points/query",
            {
                "query": vector,
                "filter": query_filter,
                "limit": limit,
                "with_payload": True,
            },
        )
        points = result.get("result", {}).get("points", result.get("result", []))
        return points if isinstance(points, list) else []

    def close(self) -> None:
        """Release an embedded Qdrant lock before a local process exits."""
        if self._local is not None:
            self._local.close()


def embedding_from_environment() -> EmbeddingModel:
    backend = os.getenv("TARCSMEM_EMBEDDING_BACKEND", "hash").lower()
    if backend == "hash":
        return HashEmbedding()
    return BGEEmbedding(os.getenv("TARCSMEM_BGE_MODEL", "BAAI/bge-small-zh-v1.5"))


def reranker_from_environment() -> Reranker | None:
    if os.getenv("TARCSMEM_RERANKER", "off").lower() == "off":
        return None
    return BGEReranker(os.getenv("TARCSMEM_RERANKER_MODEL", "BAAI/bge-reranker-base"))


def llm_from_environment(
    ollama_url: str = "http://127.0.0.1:11434",
    ollama_model: str = "qwen3:4b",
) -> LLMClient:
    """Create the configured generation client without persisting credentials."""

    provider = os.getenv("TARCSMEM_LLM_PROVIDER", "extractive").strip().lower()
    if provider in {"extractive", "demo"}:
        return ExtractiveDemoClient()
    if provider in {"ollama", "local"}:
        return OllamaClient(ollama_url, ollama_model)
    if provider == "deepseek":
        try:
            timeout = float(os.getenv("TARCSMEM_DEEPSEEK_TIMEOUT", "90"))
            retries = int(os.getenv("TARCSMEM_DEEPSEEK_MAX_RETRIES", "2"))
            max_tokens = int(os.getenv("TARCSMEM_DEEPSEEK_MAX_TOKENS", "1024"))
        except ValueError as exc:
            raise RuntimeError("DeepSeek timeout, retries and max tokens must be numeric.") from exc
        return DeepSeekClient(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("TARCSMEM_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("TARCSMEM_DEEPSEEK_MODEL", "deepseek-v4-flash"),
            timeout=timeout,
            max_retries=retries,
            max_tokens=max_tokens,
            thinking=os.getenv("TARCSMEM_DEEPSEEK_THINKING", "false").lower() == "true",
        )
    raise RuntimeError("TARCSMEM_LLM_PROVIDER must be 'extractive', 'ollama' or 'deepseek'.")
