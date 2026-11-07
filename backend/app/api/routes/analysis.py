from collections.abc import Coroutine
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.ai import ProductDetails
from app.api.deps import DbDep, SessionDep, SessionId, SessionRequired
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.client import DatabaseClient
from app.jobs import (
    JobConflictError,
    create_job,
    get_latest_job,
    job_response,
    mark_stopped,
    run_analysis,
)
from app.models import AnalyzeResponse, JobStatusResponse
from app.tracing import call_kwargs

router = APIRouter()
settings = get_settings()


def _analysis_coroutine(
    request: Request,
    db: DatabaseClient,
    session_id: str,
    job_id: str,
    product: ProductDetails,
) -> Coroutine[Any, Any, None]:
    return run_analysis(
        db=db,
        client=request.app.state.openai_client,
        params=request.app.state.llm_params,
        job_id=job_id,
        session_id=session_id,
        product=product,
        concurrency=settings.performance.openai_concurrent_requests,
        max_chars=settings.analysis.review_max_chars,
        retries=settings.analysis.scoring_retries,
        request_kwargs=call_kwargs("score"),
    )


@router.post(
    "/sessions/{session_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(settings.rate_limit.analyze_rate_limit)
async def start_analysis(
    request: Request,
    session_id: SessionId,
    session: SessionDep,
    db: DbDep,
) -> AnalyzeResponse:
    if not session.product_confirmed or session.product is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Confirm the product details before analyzing"
        )
    product = ProductDetails.model_validate(session.product)

    # One process, so a lock is enough to make "check, then insert" atomic.
    async with request.app.state.analysis_lock:
        try:
            job_id, _ = await create_job(db, session_id)
        except JobConflictError as e:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "An analysis is already running for this session"
            ) from e
        request.app.state.analysis_tasks.start(
            session_id, job_id, _analysis_coroutine(request, db, session_id, job_id, product)
        )
    return AnalyzeResponse(job_id=job_id)


@router.post(
    "/sessions/{session_id}/job/stop",
    response_model=JobStatusResponse,
    dependencies=[SessionRequired],
)
@limiter.limit(settings.rate_limit.analyze_rate_limit)
async def stop_analysis(request: Request, session_id: SessionId, db: DbDep) -> JobStatusResponse:
    """Stop the running analysis: no more requests go to the LLM server."""
    async with request.app.state.analysis_lock:
        job_id = await request.app.state.analysis_tasks.stop(session_id)
        if job_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No analysis is running for this session")
        job = await mark_stopped(db, job_id)
    if job is None:  # the session expired while it was being stopped
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
    return job_response(job)


@router.get(
    "/sessions/{session_id}/job",
    response_model=JobStatusResponse,
    dependencies=[SessionRequired],
)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def get_job(request: Request, session_id: SessionId, db: DbDep) -> JobStatusResponse:
    async with db.session() as s:
        job = await get_latest_job(s, session_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No analysis has been started")
    return job_response(job)
