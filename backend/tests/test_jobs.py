import asyncio
from datetime import timedelta

import pytest
from conftest import make_session
from fakes import FakeLLM
from sqlalchemy import func, select, update

from app.ai import LLMParams, ProductDetails
from app.cleanup import delete_expired_sessions
from app.database.models import AnalysisSession, Job, Review, Score, utcnow
from app.jobs import (
    JobConflictError,
    create_job,
    fail_interrupted_jobs,
    has_active_job,
    run_analysis,
)

PRODUCT = ProductDetails(name="Galaxy S24", aspects=["battery life", "screen"])
PARAMS = LLMParams(model="fake")


async def start(db, texts, **overrides):
    session_id = await make_session(db, texts, product=PRODUCT.model_dump())
    job_id, _ = await create_job(db, session_id)
    return session_id, job_id


async def run(db, llm, session_id, job_id, **overrides):
    kwargs = {
        "db": db,
        "client": llm,
        "params": PARAMS,
        "job_id": job_id,
        "session_id": session_id,
        "product": PRODUCT,
        "concurrency": 2,
        "max_chars": 1000,
        "retries": 1,
    }
    kwargs.update(overrides)
    await run_analysis(**kwargs)


async def get_job(db, job_id) -> Job:
    async with db.session() as s:
        return await s.get(Job, job_id)


async def reviews_by_status(db, session_id) -> dict[str, int]:
    async with db.session() as s:
        rows = await s.execute(
            select(Review.status, func.count())
            .where(Review.session_id == session_id)
            .group_by(Review.status)
        )
        return dict(rows.all())


async def test_happy_path_stores_scores_and_counts(db):
    texts = ["Great battery life", "The screen is terrible", "Nothing relevant here"]
    session_id, job_id = await start(db, texts)
    llm = FakeLLM()
    await run(db, llm, session_id, job_id)

    job = await get_job(db, job_id)
    assert (job.status, job.done, job.total, job.failed) == ("completed", 3, 3, 0)
    assert job.finished_at is not None and job.error is None
    assert await reviews_by_status(db, session_id) == {"done": 3}
    async with db.session() as s:
        rows = (
            await s.execute(
                select(Review.text, Score.aspect, Score.score).join(
                    Score, Score.review_id == Review.id
                )
            )
        ).all()
    assert sorted(rows) == [
        ("Great battery life", "battery life", 5),
        ("The screen is terrible", "screen", 1),
    ]


async def test_invalid_model_output_fails_only_that_review(db):
    session_id, job_id = await start(db, ["Great battery life", "BAD review about screen"])
    await run(db, FakeLLM(), session_id, job_id)

    job = await get_job(db, job_id)
    assert (job.status, job.done, job.failed) == ("completed", 2, 1)
    assert await reviews_by_status(db, session_id) == {"done": 1, "failed": 1}
    async with db.session() as s:
        error = await s.scalar(select(Review.error).where(Review.status == "failed"))
    assert error.startswith("Invalid model output")


async def test_job_fails_when_every_review_fails(db):
    session_id, job_id = await start(db, ["BAD one", "BAD two"])
    await run(db, FakeLLM(), session_id, job_id)
    job = await get_job(db, job_id)
    assert (job.status, job.error, job.failed) == ("failed", "Every review failed", 2)


async def test_server_outage_aborts_after_three_consecutive_failures(db):
    session_id, job_id = await start(db, [f"review {i}" for i in range(6)])
    llm = FakeLLM()
    llm.outage = True
    await run(db, llm, session_id, job_id, concurrency=1)

    job = await get_job(db, job_id)
    assert job.status == "failed"
    assert job.error == "The language model server stopped responding"
    assert (job.done, job.failed) == (3, 3)
    assert await reviews_by_status(db, session_id) == {"failed": 3, "pending": 3}
    assert len(llm.calls) == 3  # it stopped hammering the dead server


async def test_a_success_resets_the_outage_counter(db):
    session_id, job_id = await start(db, ["a", "b", "Great battery life", "c", "d", "e"])
    llm = FakeLLM()
    real_parse = llm._parse

    async def flaky(**kwargs):  # first two calls and the 4th+5th calls fail to connect
        n = len(llm.calls)
        llm.outage = n in (0, 1, 3, 4)
        return await real_parse(**kwargs)

    llm.chat.completions.parse = flaky
    await run(db, llm, session_id, job_id, concurrency=1, outage_threshold=3)
    job = await get_job(db, job_id)
    assert job.status == "completed"
    assert (job.done, job.failed) == (6, 4)


async def test_concurrency_limit_is_respected(db):
    session_id, job_id = await start(db, [f"review {i}" for i in range(12)])
    llm = FakeLLM(delay=0.01)
    await run(db, llm, session_id, job_id, concurrency=3)
    assert llm.max_inflight == 3
    assert (await get_job(db, job_id)).done == 12


async def test_cancellation_marks_the_job_interrupted(db):
    session_id, job_id = await start(db, ["Great battery life"])
    llm = FakeLLM()
    llm.gate = asyncio.Event()  # never set: the call hangs
    task = asyncio.create_task(run(db, llm, session_id, job_id))
    while not llm.calls:
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    job = await get_job(db, job_id)
    assert (job.status, job.error) == ("failed", "Interrupted")


async def test_tracing_kwargs_are_forwarded(db):
    session_id, job_id = await start(db, ["Great battery life"])
    llm = FakeLLM()
    await run(db, llm, session_id, job_id, request_kwargs={"name": "score"})
    assert llm.calls[0]["name"] == "score"


async def test_create_job_resets_earlier_results(db):
    session_id, job_id = await start(db, ["Great battery life"])
    await run(db, FakeLLM(), session_id, job_id)

    new_job_id, total = await create_job(db, session_id)
    assert new_job_id != job_id and total == 1
    async with db.session() as s:
        assert await s.scalar(select(func.count()).select_from(Score)) == 0
        assert await s.scalar(select(Review.status)) == "pending"
        assert await s.get(Job, job_id) is None  # old job rows are gone too


async def test_create_job_refuses_a_second_active_job(db):
    session_id, _ = await start(db, ["a"])
    with pytest.raises(JobConflictError):
        await create_job(db, session_id)


async def test_has_active_job_follows_the_status(db):
    session_id, job_id = await start(db, ["a"])
    async with db.session() as s:
        assert await has_active_job(s, session_id)
        await s.execute(update(Job).where(Job.id == job_id).values(status="completed"))
    async with db.session() as s:
        assert not await has_active_job(s, session_id)


async def test_fail_interrupted_jobs_only_touches_active_ones(db):
    _, job_a = await start(db, ["a"])
    _, job_b = await start(db, ["b"])
    async with db.session() as s:
        await s.execute(update(Job).where(Job.id == job_a).values(status="running"))
        await s.execute(update(Job).where(Job.id == job_b).values(status="completed"))
    assert await fail_interrupted_jobs(db) == 1
    a, b = await get_job(db, job_a), await get_job(db, job_b)
    assert (a.status, a.error) == ("failed", "Interrupted by a server restart")
    assert b.status == "completed"


async def test_cleanup_deletes_expired_sessions_but_not_busy_or_fresh_ones(db):
    old_idle = await make_session(db, ["x"])
    old_busy, _ = await start(db, ["y"])  # has a pending job
    fresh = await make_session(db, ["z"])
    long_ago = utcnow() - timedelta(hours=10)
    async with db.session() as s:
        await s.execute(
            update(AnalysisSession)
            .where(AnalysisSession.id.in_([old_idle, old_busy]))
            .values(created_at=long_ago)
        )

    assert await delete_expired_sessions(db, ttl_hours=6) == 1
    async with db.session() as s:
        remaining = set((await s.scalars(select(AnalysisSession.id))).all())
        assert remaining == {old_busy, fresh}
        # cascade removed the deleted session's reviews
        assert await s.scalar(
            select(func.count()).select_from(Review).where(Review.session_id == old_idle)
        ) == 0
