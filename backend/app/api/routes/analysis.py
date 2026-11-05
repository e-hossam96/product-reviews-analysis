from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.ai import ProductDetails
from app.api.deps import DbDep, SessionId, SessionRequired
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.models import AnalysisSession
from app.jobs import (
    JobConflictError,
    create_job,
    get_latest_job,
    job_response,
    run_analysis,
)
from app.models import AnalyzeResponse, JobStatusResponse
from app.tracing import call_kwargs

router = APIRouter()
settings = get_settings()


@router.post(
    "/sessions/{session_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[SessionRequired],
)
@limiter.limit(settings.rate_limit.analyze_rate_limit)
async def start_analysis(
    request: Request,
    session_id: SessionId,
    background_tasks: BackgroundTasks,
    db: DbDep,
) -> AnalyzeResponse:
    async with db.session() as s:
        row = await s.get(AnalysisSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
        if not row.product_confirmed or row.product is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Confirm the product details before analyzing"
            )
        product = ProductDetails.model_validate(row.product)

    # One process, so a lock is enough to make "check, then insert" atomic.
    async with request.app.state.analysis_lock:
        try:
            job_id, _total = await create_job(db, session_id)
        except JobConflictError as e:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "An analysis is already running for this session",
            ) from e

    background_tasks.add_task(
        run_analysis,
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
    return AnalyzeResponse(job_id=job_id)


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
