from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from sqlalchemy import select

from app.ai import ProductDetails, extract_product_details
from app.api.deps import DbDep, SessionId, SessionRequired, llm_errors
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.models import AnalysisSession, Review
from app.ingest import IngestError, parse_reviews, sample_reviews
from app.jobs import get_latest_job, has_active_job, invalidate_analysis, job_response
from app.models import (
    ConfirmProductRequest,
    ConfirmProductResponse,
    ExtractResponse,
    SessionCreateResponse,
    SessionStateResponse,
)
from app.ngrams import top_ngrams
from app.tracing import call_kwargs, trace_session
from app.utils import logger

router = APIRouter()
settings = get_settings()

_BUSY = "An analysis is running for this session. Wait for it to finish."


@router.post(
    "/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(settings.rate_limit.upload_rate_limit)
async def create_session(
    request: Request, file: UploadFile, db: DbDep
) -> SessionCreateResponse:
    max_bytes = settings.session.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)  # never buffer more than the limit
    try:
        parsed = parse_reviews(data, max_rows=settings.session.max_rows, max_bytes=max_bytes)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e

    texts = [r.text for r in parsed.reviews]
    grams = top_ngrams(
        texts, max_n=settings.analysis.ngram_max_n, top_k=settings.analysis.ngram_top_k
    )
    async with db.session() as s:
        session = AnalysisSession(source_filename=(file.filename or "")[-255:] or None)
        s.add(session)
        await s.flush()
        s.add_all(
            Review(session_id=session.id, row_index=r.row_index, text=r.text)
            for r in parsed.reviews
        )
        session_id = session.id
    logger.info(
        "Session created | reviews=%d skipped_empty=%d",
        len(parsed.reviews),
        parsed.skipped_empty,
    )
    return SessionCreateResponse(
        session_id=session_id,
        review_count=len(parsed.reviews),
        skipped_empty=parsed.skipped_empty,
        top_ngrams=grams,
    )


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def get_session_state(
    request: Request, session_id: SessionId, db: DbDep
) -> SessionStateResponse:
    """Where the session stands, so a reloaded page can pick up where it left off."""
    async with db.session() as s:
        row = await s.get(AnalysisSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
        texts = list(
            (
                await s.scalars(
                    select(Review.text)
                    .where(Review.session_id == session_id)
                    .order_by(Review.row_index)
                )
            ).all()
        )
        job = await get_latest_job(s, session_id)

    return SessionStateResponse(
        filename=row.source_filename,
        review_count=len(texts),
        top_ngrams=top_ngrams(
            texts,
            max_n=settings.analysis.ngram_max_n,
            top_k=settings.analysis.ngram_top_k,
        ),
        product=ProductDetails.model_validate(row.product) if row.product else None,
        product_confirmed=row.product_confirmed,
        job=job_response(job) if job else None,
    )


@router.post(
    "/sessions/{session_id}/extract",
    response_model=ExtractResponse,
    dependencies=[SessionRequired],
)
@limiter.limit(settings.rate_limit.extract_rate_limit)
async def extract_product(
    request: Request, session_id: SessionId, db: DbDep
) -> ExtractResponse:
    async with db.session() as s:
        if await has_active_job(s, session_id):
            raise HTTPException(status.HTTP_409_CONFLICT, _BUSY)
        texts = list(
            (
                await s.scalars(
                    select(Review.text)
                    .where(Review.session_id == session_id)
                    .order_by(Review.row_index)
                )
            ).all()
        )

    grams = top_ngrams(
        texts, max_n=settings.analysis.ngram_max_n, top_k=settings.analysis.ngram_top_k
    )
    samples = sample_reviews(
        texts,
        k=settings.analysis.extraction_sample_size,
        max_chars=settings.analysis.extraction_sample_chars,
    )
    # The slow LLM call runs outside any database transaction.
    with llm_errors(), trace_session(session_id, "extract"):
        product = await extract_product_details(
            request.app.state.openai_client,
            request.app.state.llm_params,
            ngrams=[(g.ngram, g.count) for g in grams],
            sample_reviews=samples,
            retries=settings.analysis.scoring_retries,
            request_kwargs=call_kwargs("extract"),
        )

    async with db.session() as s:
        row = await s.get(AnalysisSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
        if await has_active_job(s, session_id):
            raise HTTPException(status.HTTP_409_CONFLICT, _BUSY)
        await invalidate_analysis(s, session_id)
        row.product = product.model_dump()
        row.product_confirmed = False
    return ExtractResponse(product=product)


@router.put("/sessions/{session_id}/product", response_model=ConfirmProductResponse)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def confirm_product(
    request: Request,
    session_id: SessionId,
    body: ConfirmProductRequest,
    db: DbDep,
) -> ConfirmProductResponse:
    """Save the user's confirmed product details. Also works without a prior extract,
    so the user can type the details in by hand."""
    new_product: ProductDetails = body.product
    async with db.session() as s:
        row = await s.get(AnalysisSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
        if await has_active_job(s, session_id):
            raise HTTPException(status.HTTP_409_CONFLICT, _BUSY)
        if row.product != new_product.model_dump():
            await invalidate_analysis(s, session_id)  # earlier scores are now stale
        row.product = new_product.model_dump()
        row.product_confirmed = True
    return ConfirmProductResponse(product=new_product)
