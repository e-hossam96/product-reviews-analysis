import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.ai import LLMParams
from app.api.main import api_router
from app.cleanup import cleanup_loop
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.client import DatabaseClient
from app.jobs import AnalysisTasks, fail_interrupted_jobs
from app.utils import logger

settings = get_settings()


def build_openai_client() -> AsyncOpenAI:
    """Plain client, or the Langfuse drop-in that traces every call."""
    if settings.langfuse.enabled:
        from langfuse.openai import AsyncOpenAI as TracedAsyncOpenAI

        client_cls: type[AsyncOpenAI] = TracedAsyncOpenAI
        logger.info("Langfuse tracing enabled | host=%s", settings.langfuse.host)
    else:
        client_cls = AsyncOpenAI
    cfg = settings.openai
    return client_cls(
        api_key=cfg.api_key.get_secret_value(),
        base_url=cfg.api_base,
        timeout=cfg.timeout_seconds,
        max_retries=cfg.max_retries,
    )


def build_llm_params() -> LLMParams:
    cfg = settings.openai
    return LLMParams(
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_completion_tokens,
        seed=cfg.seed,
    )


def flush_langfuse() -> None:
    if not settings.langfuse.enabled:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.exception("Could not flush Langfuse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up %s v%s", settings.application.name, settings.application.version)
    logger.debug(
        "LLM client | model=%s base_url=%s", settings.openai.model_name, settings.openai.api_base
    )

    app.state.db = DatabaseClient(settings.database)
    app.state.openai_client = build_openai_client()
    app.state.llm_params = build_llm_params()
    app.state.analysis_lock = asyncio.Lock()
    app.state.analysis_tasks = AnalysisTasks()

    interrupted = await fail_interrupted_jobs(app.state.db)
    if interrupted:
        logger.warning("Marked %d interrupted job(s) as failed", interrupted)
    cleanup_task = asyncio.create_task(
        cleanup_loop(
            app.state.db,
            ttl_hours=settings.session.ttl_hours,
            interval_minutes=settings.session.cleanup_interval_minutes,
        )
    )
    logger.info("Application startup complete — ready to serve requests")
    yield

    logger.info("Shutting down")
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    await app.state.analysis_tasks.shutdown()  # running jobs are recorded as interrupted
    await app.state.openai_client.close()
    flush_langfuse()
    await app.state.db.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.application.name,
    lifespan=lifespan,
    generate_unique_id_function=lambda route: f"{route.tags[0] if route.tags else ''}-{route.name}",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allowed_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allowed_methods,
    allow_headers=settings.cors.allowed_headers,
)


@app.middleware("http")
async def log_request_timing(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    # Log the route template, never the real path: the session id in the path is an
    # access token and must not end up in log files.
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    logger.info(
        "%s %s | status=%d | %.1fms | %s",
        request.method,
        path,
        response.status_code,
        (time.perf_counter() - start) * 1000,
        datetime.now(UTC).isoformat(timespec="seconds"),
    )
    return response


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="127.0.0.1", port=11696, log_level="info", reload=True, workers=1
    )
