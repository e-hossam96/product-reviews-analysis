import pytest
from app.core.config import DatabaseSettings
from app.database.client import DatabaseClient
from app.database.models import AnalysisSession, Base, Job, Review, Score
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
async def db(tmp_path):
    client = DatabaseClient(DatabaseSettings(path=(tmp_path / "test.db").as_posix()))
    async with client.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield client
    await client.close()


async def seed(db: DatabaseClient) -> str:
    async with db.session() as s:
        session = AnalysisSession(source_filename="reviews.csv")
        s.add(session)
        await s.flush()
        review = Review(session_id=session.id, row_index=0, text="Great battery")
        s.add(review)
        await s.flush()
        s.add(
            Score(
                review_id=review.id,
                session_id=session.id,
                aspect="battery life",
                score=5,
            )
        )
        s.add(Job(session_id=session.id, total=1))
    return session.id


async def count(db: DatabaseClient, model) -> int:
    async with db.session() as s:
        return await s.scalar(select(func.count()).select_from(model))


async def test_pragmas_applied(db):
    async with db.session() as s:
        assert await s.scalar(text("PRAGMA foreign_keys")) == 1
        assert (await s.scalar(text("PRAGMA journal_mode"))).lower() == "wal"
        assert await s.scalar(text("PRAGMA busy_timeout")) == 5000


async def test_defaults(db):
    sid = await seed(db)
    async with db.session() as s:
        session = await s.get(AnalysisSession, sid)
        assert len(session.id) >= 43
        assert session.product_confirmed is False
        assert session.product is None
        assert session.created_at is not None
        job = (await s.scalars(select(Job))).one()
        assert (job.status, job.done, job.failed) == ("pending", 0, 0)
        review = (await s.scalars(select(Review))).one()
        assert review.status == "pending"


async def test_missing_product_is_sql_null(db):
    await seed(db)
    async with db.session() as s:
        found = await s.scalars(select(AnalysisSession.id).where(AnalysisSession.product.is_(None)))
        assert len(found.all()) == 1


async def test_product_json_roundtrip_keeps_non_ascii(db):
    sid = await seed(db)
    product = {"name": "Café Latte", "aspects": ["crème", "battery life"]}
    async with db.session() as s:
        (await s.get(AnalysisSession, sid)).product = product
    async with db.session() as s:
        assert (await s.get(AnalysisSession, sid)).product == product


async def test_deleting_session_cascades(db):
    sid = await seed(db)
    async with db.session() as s:
        await s.execute(delete(AnalysisSession).where(AnalysisSession.id == sid))
    for model in (Review, Score, Job):
        assert await count(db, model) == 0


async def test_one_score_per_review_and_aspect(db):
    sid = await seed(db)
    with pytest.raises(IntegrityError):
        async with db.session() as s:
            review = (await s.scalars(select(Review))).one()
            s.add(Score(review_id=review.id, session_id=sid, aspect="battery life", score=2))
            await s.flush()


@pytest.mark.parametrize("bad", [0, 6])
async def test_score_must_be_in_range(db, bad):
    sid = await seed(db)
    with pytest.raises(IntegrityError):
        async with db.session() as s:
            review = (await s.scalars(select(Review))).one()
            s.add(Score(review_id=review.id, session_id=sid, aspect="screen", score=bad))
            await s.flush()


async def test_session_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        async with db.session() as s:
            s.add(AnalysisSession())
            await s.flush()
            raise RuntimeError("boom")
    assert await count(db, AnalysisSession) == 0
