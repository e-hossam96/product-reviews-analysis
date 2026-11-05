import pytest

from app.core.config import DatabaseSettings
from app.core.limiter import limiter
from app.database.client import DatabaseClient
from app.database.models import AnalysisSession, Base, Review


@pytest.fixture
async def db(tmp_path):
    client = DatabaseClient(DatabaseSettings(path=(tmp_path / "test.db").as_posix()))
    async with client.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield client
    await client.close()


@pytest.fixture(autouse=True)
def _rate_limits_off():
    limiter.enabled = False
    yield
    limiter.enabled = True
    limiter.reset()


async def make_session(
    db: DatabaseClient,
    texts: list[str],
    *,
    product: dict | None = None,
    confirmed: bool = True,
) -> str:
    async with db.session() as s:
        session = AnalysisSession(product=product, product_confirmed=confirmed)
        s.add(session)
        await s.flush()
        s.add_all(
            Review(session_id=session.id, row_index=i, text=t) for i, t in enumerate(texts)
        )
        return session.id
