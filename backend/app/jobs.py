import asyncio
from typing import Any

import openai
from openai import AsyncOpenAI
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import LLMOutputError, LLMParams, ProductDetails, score_review
from app.ai.schemas import AspectMention
from app.database.client import DatabaseClient
from app.database.models import Job, Review, ReviewStatus, Score, utcnow
from app.models import JobStatus, JobStatusResponse
from app.tracing import trace_session
from app.utils import logger

ACTIVE_STATUSES = (JobStatus.PENDING.value, JobStatus.RUNNING.value)
OUTAGE_THRESHOLD = 3  # consecutive connection failures before the job gives up
MAX_ERROR_CHARS = 300


class JobConflictError(RuntimeError):
    """An analysis is already pending or running for this session."""


async def has_active_job(s: AsyncSession, session_id: str) -> bool:
    found = await s.scalar(
        select(Job.id)
        .where(Job.session_id == session_id, Job.status.in_(ACTIVE_STATUSES))
        .limit(1)
    )
    return found is not None


async def get_latest_job(s: AsyncSession, session_id: str) -> Job | None:
    return (
        await s.scalars(
            select(Job)
            .where(Job.session_id == session_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
    ).first()


def job_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        done=job.done,
        total=job.total,
        failed=job.failed,
        error=job.error,
    )


async def invalidate_analysis(s: AsyncSession, session_id: str) -> None:
    """Forget earlier results, because the product details they rest on changed."""
    await s.execute(delete(Score).where(Score.session_id == session_id))
    await s.execute(delete(Job).where(Job.session_id == session_id))
    await s.execute(
        update(Review)
        .where(Review.session_id == session_id)
        .values(status=ReviewStatus.PENDING.value, error=None)
    )


async def create_job(db: DatabaseClient, session_id: str) -> tuple[str, int]:
    """Reset any earlier results and register a pending job. Returns (job_id, total)."""
    async with db.session() as s:
        if await has_active_job(s, session_id):
            raise JobConflictError(session_id)
        await invalidate_analysis(s, session_id)
        total = await s.scalar(
            select(func.count()).select_from(Review).where(Review.session_id == session_id)
        )
        job = Job(session_id=session_id, total=total or 0)
        s.add(job)
        await s.flush()
        return job.id, job.total


async def fail_interrupted_jobs(db: DatabaseClient) -> int:
    """Jobs left pending or running by a previous process can never finish."""
    async with db.session() as s:
        result = await s.execute(
            update(Job)
            .where(Job.status.in_(ACTIVE_STATUSES))
            .values(
                status=JobStatus.FAILED.value,
                error="Interrupted by a server restart",
                finished_at=utcnow(),
            )
        )
        return result.rowcount or 0


async def _mark_done(
    db: DatabaseClient,
    job_id: str,
    session_id: str,
    review_id: int,
    mentions: list[AspectMention],
) -> None:
    async with db.session() as s:
        s.add_all(
            Score(
                review_id=review_id,
                session_id=session_id,
                aspect=m.aspect,
                score=m.score,
            )
            for m in mentions
        )
        await s.execute(
            update(Review)
            .where(Review.id == review_id)
            .values(status=ReviewStatus.DONE.value, error=None)
        )
        await s.execute(update(Job).where(Job.id == job_id).values(done=Job.done + 1))


async def _mark_failed(db: DatabaseClient, job_id: str, review_id: int, error: str) -> None:
    async with db.session() as s:
        await s.execute(
            update(Review)
            .where(Review.id == review_id)
            .values(status=ReviewStatus.FAILED.value, error=error[:MAX_ERROR_CHARS])
        )
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(done=Job.done + 1, failed=Job.failed + 1)
        )


async def _finish(
    db: DatabaseClient, job_id: str, status: JobStatus, error: str | None = None
) -> None:
    async with db.session() as s:
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=status.value, error=error, finished_at=utcnow())
        )


async def run_analysis(
    *,
    db: DatabaseClient,
    client: AsyncOpenAI,
    params: LLMParams,
    job_id: str,
    session_id: str,
    product: ProductDetails,
    concurrency: int,
    max_chars: int,
    retries: int,
    request_kwargs: dict[str, Any] | None = None,
    outage_threshold: int = OUTAGE_THRESHOLD,
) -> None:
    """Score every pending review of a session. Never raises, except on cancellation.

    A review that can't be scored is recorded as failed and the job carries on. The
    job only gives up when the LLM server stops answering (several connection
    failures in a row) or the database breaks.
    """
    try:
        async with db.session() as s:
            await s.execute(
                update(Job).where(Job.id == job_id).values(status=JobStatus.RUNNING.value)
            )
            rows = (
                await s.execute(
                    select(Review.id, Review.text)
                    .where(
                        Review.session_id == session_id,
                        Review.status == ReviewStatus.PENDING.value,
                    )
                    .order_by(Review.row_index)
                )
            ).all()

        queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        for review_id, text in rows:
            queue.put_nowait((review_id, text))

        abort = asyncio.Event()
        fatal: str | None = None
        outages = 0

        async def process(review_id: int, text: str) -> None:
            nonlocal fatal, outages
            try:
                with trace_session(session_id, "score"):
                    result = await score_review(
                        client,
                        params,
                        product=product,
                        review_text=text,
                        max_chars=max_chars,
                        retries=retries,
                        request_kwargs=request_kwargs,
                    )
            except LLMOutputError as e:
                outages = 0
                await _mark_failed(db, job_id, review_id, f"Invalid model output: {e}")
            except openai.APIConnectionError:
                outages += 1
                await _mark_failed(db, job_id, review_id, "The language model server is unreachable")
                if outages >= outage_threshold:
                    fatal = "The language model server stopped responding"
                    abort.set()
            except openai.OpenAIError as e:
                outages = 0
                await _mark_failed(db, job_id, review_id, f"{type(e).__name__}: {e}")
            else:
                outages = 0
                await _mark_done(db, job_id, session_id, review_id, result.mentions)

        async def worker() -> None:
            nonlocal fatal
            while not abort.is_set():
                try:
                    review_id, text = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await process(review_id, text)
                except Exception as e:  # database trouble: stop the whole job
                    logger.exception("Job %s: unrecoverable error", job_id)
                    fatal = f"Internal error: {type(e).__name__}"
                    abort.set()

        workers = max(1, min(concurrency, len(rows)))
        await asyncio.gather(*(worker() for _ in range(workers)))

        if fatal:
            await _finish(db, job_id, JobStatus.FAILED, fatal)
            return
        async with db.session() as s:
            job = await s.get(Job, job_id)
        if job is not None and job.total > 0 and job.failed >= job.total:
            await _finish(db, job_id, JobStatus.FAILED, "Every review failed")
        else:
            await _finish(db, job_id, JobStatus.COMPLETED)
        logger.info("Job %s finished", job_id)
    except asyncio.CancelledError:
        await _finish(db, job_id, JobStatus.FAILED, "Interrupted")
        raise
    except Exception as e:
        logger.exception("Job %s crashed", job_id)
        try:
            await _finish(db, job_id, JobStatus.FAILED, f"Internal error: {type(e).__name__}")
        except Exception:
            logger.exception("Job %s: could not record the failure", job_id)
