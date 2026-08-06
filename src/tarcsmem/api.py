import hashlib
import hmac
import json
import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import RLock
from time import monotonic, time
from uuid import uuid4

from . import __version__
from .models import AccessContext, MemoryRecord
from .service import TARCSMemoryService

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


@dataclass(frozen=True, slots=True)
class ApiRuntimePolicy:
    """Small, dependency-free safeguards for a single API process.

    A production gateway should enforce distributed rate limits before traffic
    reaches the application. This guard is still useful for local and pilot
    deployments, but is intentionally keyed only by the direct peer address.
    """

    requests_per_minute: int = 120
    idempotency_ttl_seconds: int = 86_400

    @classmethod
    def from_environment(cls) -> "ApiRuntimePolicy":
        try:
            rate = int(os.getenv("TARCSMEM_RATE_LIMIT_REQUESTS_PER_MINUTE", "120"))
            ttl_hours = int(os.getenv("TARCSMEM_IDEMPOTENCY_TTL_HOURS", "24"))
        except ValueError as exc:
            raise RuntimeError("API rate-limit and idempotency settings must be integers") from exc
        if rate <= 0 or ttl_hours <= 0 or ttl_hours > 168:
            raise RuntimeError(
                "API rate limit must be positive and idempotency TTL must be 1..168 hours"
            )
        return cls(rate, ttl_hours * 3_600)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = RLock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_key: str) -> tuple[bool, int]:
        now = monotonic()
        with self._lock:
            window = self._requests[client_key]
            while window and now - window[0] >= self.window_seconds:
                window.popleft()
            if len(window) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - window[0])) + 1)
                return False, retry_after
            window.append(now)
            return True, 0


def create_app(
    db_path: str = "./data/tarcsmem.db",
    api_key: str | None = None,
    chat_agent: object | None = None,
    runtime_policy: ApiRuntimePolicy | None = None,
):
    try:
        from fastapi import FastAPI, Header, HTTPException, Request, Response
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install API extras: pip install -e '.[api]'") from exc

    app = FastAPI(title="TARCS-Mem", version=__version__)
    service = TARCSMemoryService(db_path)
    app.state.tarcsmem_service = service
    # Agent dependencies are optional. Keep deterministic governance endpoints
    # usable in a minimal API installation, then construct the conversational
    # path only when /v1/chat is requested.
    app.state.tarcsmem_chat_agent = chat_agent
    configured_key = api_key if api_key is not None else os.getenv("TARCSMEM_API_KEY", "")
    app.state.tarcsmem_runtime_policy = runtime_policy or ApiRuntimePolicy.from_environment()
    limiter = SlidingWindowRateLimiter(app.state.tarcsmem_runtime_policy.requests_per_minute)

    @app.middleware("http")
    async def api_guardrails(request: Request, call_next):
        request_id = request.headers.get("x-request-id", "")
        request_id = request_id if _REQUEST_ID.fullmatch(request_id) else uuid4().hex
        is_public_liveness = request.url.path == "/healthz"
        if configured_key and not is_public_liveness:
            authorization = request.headers.get("authorization", "")
            supplied = (
                authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            )
            if not supplied or not hmac.compare_digest(supplied, configured_key):
                response = JSONResponse(
                    status_code=401, content={"detail": "valid bearer token required"}
                )
                response.headers["X-Request-ID"] = request_id
                return response
        if not is_public_liveness:
            client_key = request.client.host if request.client else "unknown"
            allowed, retry_after = limiter.allow(client_key)
            if not allowed:
                service.observability.metrics.increment(
                    "tarcsmem_api_rate_limit_total", labels={"outcome": "blocked"}
                )
                response = JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-Request-ID"] = request_id
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    class IngestRequest(BaseModel):
        record: dict

    class QueryRequest(BaseModel):
        question: str = Field(min_length=1, max_length=4000)
        as_of: date
        tenant_id: str = Field(default="default", min_length=1, max_length=200)
        roles: list[str] = Field(default_factory=list, max_length=100)

    class ConversationMessage(BaseModel):
        role: str = Field(pattern="^(user|assistant)$")
        content: str = Field(min_length=1, max_length=1200)

    class ChatRequest(QueryRequest):
        conversation: list[ConversationMessage] = Field(default_factory=list, max_length=6)

    class CompatibleMessage(BaseModel):
        role: str = Field(pattern="^(system|user|assistant)$")
        content: str = Field(min_length=1, max_length=4000)

    class CompatibleChatRequest(BaseModel):
        model: str = Field(default="tarcsmem-governed", min_length=1, max_length=200)
        messages: list[CompatibleMessage] = Field(min_length=1, max_length=20)
        stream: bool = False
        as_of: date | None = None
        tenant_id: str = Field(default="default", min_length=1, max_length=200)
        roles: list[str] = Field(default_factory=list, max_length=100)

    class ReviewRequest(BaseModel):
        decision: str = Field(pattern="^(approve|reject)$")
        reviewer: str = Field(min_length=1, max_length=200)
        note: str = Field(default="", max_length=2000)

    @app.get("/healthz")
    def healthz():
        # Keep the unauthenticated liveness response free of tenant or inventory metadata.
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        if not service.store.is_ready():
            raise HTTPException(status_code=503, detail="storage is not ready")
        return {"status": "ready"}

    def idempotency_response(
        request_path: str,
        idempotency_key: str | None,
        body: dict[str, object],
        operation,
        success_status: int,
    ):
        if not idempotency_key:
            return JSONResponse(status_code=success_status, content=operation())
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key must be 8..128 letters, digits, underscores or hyphens",
            )
        canonical = json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
        fingerprint = hashlib.sha256(f"{request_path}:{canonical}".encode()).hexdigest()
        state, cached = service.store.idempotency_begin(
            idempotency_key,
            fingerprint,
            app.state.tarcsmem_runtime_policy.idempotency_ttl_seconds,
        )
        if state == "replay":
            service.observability.metrics.increment(
                "tarcsmem_api_idempotency_total", labels={"outcome": "replayed"}
            )
            return JSONResponse(status_code=success_status, content=cached)
        if state == "conflict":
            raise HTTPException(
                status_code=409, detail="Idempotency-Key was already used with another request"
            )
        if state == "in_progress":
            raise HTTPException(
                status_code=409, detail="Idempotency-Key request is still in progress"
            )
        try:
            response = operation()
        except Exception:
            service.store.idempotency_abandon(idempotency_key)
            raise
        service.store.idempotency_complete(idempotency_key, response)
        service.observability.metrics.increment(
            "tarcsmem_api_idempotency_total", labels={"outcome": "completed"}
        )
        return JSONResponse(status_code=success_status, content=response)

    @app.post("/v1/memories", status_code=201)
    def ingest(
        request: IngestRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        def operation() -> dict[str, object]:
            record_value = MemoryRecord.from_dict(request.record)
            agent = app.state.tarcsmem_chat_agent
            record = (
                agent.ingest_record(record_value)
                if agent is not None
                else service.ingest(record_value)
            )
            return record.to_dict()

        try:
            return idempotency_response(
                "/v1/memories", idempotency_key, {"record": request.record}, operation, 201
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/query")
    def query(request: QueryRequest):
        access = AccessContext.from_values(request.tenant_id, request.roles)
        return service.query(request.question, request.as_of, access).to_dict()

    def get_chat_agent():
        agent = app.state.tarcsmem_chat_agent
        if agent is not None:
            return agent
        try:
            from .agent import LocalAgentConfig, TARCSChatAgent

            agent = TARCSChatAgent(
                LocalAgentConfig.from_environment(db_path),
                memory=service,
            )
        except (ImportError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "conversational agent is unavailable; install '.[api,ui,cloud]' and "
                    "configure its embedding, vector and LLM provider. "
                    f"Reason: {exc}"
                ),
            ) from exc
        app.state.tarcsmem_chat_agent = agent
        return agent

    @app.post("/v1/chat")
    def chat(request: ChatRequest):
        """Run generated answers only after the same TARCS governed retrieval path."""
        agent = get_chat_agent()
        access = AccessContext.from_values(request.tenant_id, request.roles)
        return agent.chat(
            request.question,
            request.as_of,
            [message.model_dump() for message in request.conversation],
            access,
        )

    @app.get("/v1/models")
    def compatible_models():
        """Advertise the governed gateway as an OpenAI-compatible model target."""
        return {
            "object": "list",
            "data": [
                {
                    "id": "tarcsmem-governed",
                    "object": "model",
                    "created": 0,
                    "owned_by": "tarcsmem",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    def compatible_chat(request: CompatibleChatRequest):
        """Non-streaming OpenAI-compatible facade over the governed chat path.

        Client-supplied system messages are deliberately not forwarded: they
        cannot replace the server-owned evidence, citation or egress policy.
        TARCS details are returned in an additive extension field.
        """
        if request.stream:
            raise HTTPException(
                status_code=400,
                detail="stream=true is not supported; retry with stream=false",
            )
        messages = [message.model_dump() for message in request.messages]
        last_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index]["role"] == "user"
            ),
            None,
        )
        if last_user_index is None:
            raise HTTPException(status_code=422, detail="at least one user message is required")
        last_user = messages[last_user_index]
        conversation = [
            item for item in messages[:last_user_index] if item["role"] in {"user", "assistant"}
        ][-6:]
        access = AccessContext.from_values(request.tenant_id, request.roles)
        result = get_chat_agent().chat(
            last_user["content"],
            request.as_of or datetime.now(tz=UTC).date(),
            conversation,
            access,
        )
        generation = result.get("generation_metrics", {})
        prompt_tokens = int(generation.get("prompt_tokens", generation.get("input_tokens", 0)))
        completion_tokens = int(
            generation.get("completion_tokens", generation.get("output_tokens", 0))
        )
        return {
            "id": f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion",
            "created": int(time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": str(result["answer"])},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "tarcsmem": {
                "outcome": result.get("outcome"),
                "citations": result.get("citations", []),
                "decision_trace": result.get("decision_trace", {}),
                "observability": result.get("observability", {}),
                "ignored_system_messages": sum(1 for item in messages if item["role"] == "system"),
            },
        }

    @app.get("/v1/observability")
    def observability(limit: int = 50):
        return {
            "metrics": service.observability.metrics.snapshot(),
            "recent_spans": service.observability.tracer.buffer.recent(limit),
            "privacy": "raw questions, documents and credentials are never captured in traces",
        }

    @app.get("/metrics")
    def prometheus_metrics():
        return Response(
            content=service.observability.metrics.prometheus_text(),
            media_type="text/plain; version=0.0.4",
        )

    @app.get("/v1/memories/{record_id}/audit")
    def audit(record_id: str):
        if service.store.get(record_id) is None:
            raise HTTPException(status_code=404, detail="memory record not found")
        return {"record_id": record_id, "events": service.audit_trail(record_id)}

    @app.post("/v1/memories/{record_id}/review")
    def review(
        record_id: str,
        request: ReviewRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        def operation() -> dict[str, object]:
            return service.review(
                record_id,
                decision=request.decision,
                reviewer=request.reviewer,
                note=request.note,
            ).to_dict()

        try:
            return idempotency_response(
                f"/v1/memories/{record_id}/review",
                idempotency_key,
                request.model_dump(),
                operation,
                200,
            )
        except ValueError as exc:
            message = str(exc)
            status_code = 404 if message == "memory record not found" else 409
            raise HTTPException(status_code=status_code, detail=message) from exc

    return app
