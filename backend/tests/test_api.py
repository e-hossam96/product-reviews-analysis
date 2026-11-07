import asyncio
import csv
import io
import logging

import httpx
import pytest
from fakes import FakeLLM
from pydantic import SecretStr
from sqlalchemy import func, select

from app import main
from app.api.routes import health as health_routes
from app.api.routes import sessions as sessions_routes
from app.core.config import DatabaseSettings, Settings
from app.core.limiter import limiter
from app.database.client import DatabaseClient
from app.database.models import AnalysisSession, Base, Job, Review, Score
from app.utils import logger as app_logger

REVIEWS_CSV = (
    "id,text\n"
    "1,Great battery life and a great screen\n"
    "2,The screen is terrible\n"
    "3,Shipping was quick\n"
    '4,"=HYPERLINK(""http://evil.test"") battery life"\n'
    "5,\n"
)
API = "/api/v1"


@pytest.fixture
async def llm():
    return FakeLLM()


@pytest.fixture
async def client(tmp_path, monkeypatch, llm):
    """The real app (lifespan, middleware, routers) over a temp DB and the fake LLM."""
    path = (tmp_path / "api.db").as_posix()
    monkeypatch.setattr(main, "settings", Settings(database=DatabaseSettings(path=path)))
    setup = DatabaseClient(DatabaseSettings(path=path))
    async with setup.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await setup.close()

    async with main.app.router.lifespan_context(main.app):
        await main.app.state.openai_client.close()  # the real client is not used
        main.app.state.openai_client = llm
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            c.db = main.app.state.db
            yield c


def csv_file(content: str = REVIEWS_CSV, name: str = "reviews.csv"):
    return {"file": (name, content.encode("utf-8"), "text/csv")}


async def upload(client, content: str = REVIEWS_CSV) -> str:
    response = await client.post(f"{API}/sessions", files=csv_file(content))
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


async def confirm(client, session_id, aspects=("battery life", "screen")) -> None:
    response = await client.put(
        f"{API}/sessions/{session_id}/product",
        json={"product": {"name": "Galaxy S24", "aspects": list(aspects)}},
    )
    assert response.status_code == 200, response.text


async def analyze(client, session_id) -> dict:
    """Start an analysis and wait for it to finish."""
    response = await client.post(f"{API}/sessions/{session_id}/analyze")
    assert response.status_code == 202, response.text
    task = main.app.state.analysis_tasks.get(session_id)
    if task is not None:
        await asyncio.wait([task])
    job = (await client.get(f"{API}/sessions/{session_id}/job")).json()
    return job


# --- basics --------------------------------------------------------------------
async def test_health_and_config(client):
    health = (await client.get(f"{API}/health")).json()
    assert health["status"] == "ok" and health["application_name"] == "reviews-analysis"
    config = (await client.get(f"{API}/config")).json()
    assert config["max_rows"] == 100 and config["max_aspects"] == 10
    assert config["estimated_seconds_per_review"] > 0
    assert config["tracing_enabled"] is False


async def test_config_reports_when_tracing_is_on(client, monkeypatch):
    langfuse = health_routes.settings.langfuse
    monkeypatch.setattr(langfuse, "public_key", "pk-test")
    monkeypatch.setattr(langfuse, "secret_key", SecretStr("sk-test"))
    assert (await client.get(f"{API}/config")).json()["tracing_enabled"] is True


async def test_lifespan_wires_state_and_shuts_down(client, llm):
    state = main.app.state
    assert state.db is client.db and state.analysis_lock is not None
    assert state.llm_params.model == main.settings.openai.model_name


# --- upload ----------------------------------------------------------------------
async def test_upload_returns_ngrams_and_counts(client):
    csv_text = "text\n" + "Great battery life\n" * 3 + "\n"
    response = await client.post(f"{API}/sessions", files=csv_file(csv_text))
    body = response.json()
    assert response.status_code == 201
    assert body["review_count"] == 3 and body["skipped_empty"] == 0
    assert body["top_ngrams"] == [{"ngram": "great battery life", "count": 3}]
    assert len(body["session_id"]) >= 43


async def test_upload_counts_skipped_empty_rows(client):
    response = await client.post(f"{API}/sessions", files=csv_file())
    body = response.json()
    assert (body["review_count"], body["skipped_empty"]) == (4, 1)


@pytest.mark.parametrize(
    "content, message",
    [
        ("id,review\n1,hello\n", "Missing required column 'text'"),
        ("", "The file is empty"),
        ("text\n \n", "No non-empty reviews"),
    ],
)
async def test_upload_rejects_unusable_files(client, content, message):
    response = await client.post(f"{API}/sessions", files=csv_file(content))
    assert response.status_code == 422
    assert message in response.json()["detail"]


async def test_upload_rejects_too_many_rows(client, monkeypatch):
    monkeypatch.setattr(sessions_routes.settings.session, "max_rows", 2)
    response = await client.post(f"{API}/sessions", files=csv_file("text\na\nb\nc\n"))
    assert response.status_code == 422
    assert "more than 2 rows" in response.json()["detail"]


async def test_upload_rejects_oversized_files(client, monkeypatch):
    monkeypatch.setattr(sessions_routes.settings.session, "max_upload_mb", 1)
    big = "text\n" + ("x" * 100 + "\n") * 12_000
    response = await client.post(f"{API}/sessions", files=csv_file(big))
    assert response.status_code == 422
    assert "larger than" in response.json()["detail"]


async def test_upload_without_a_file_is_a_validation_error(client):
    assert (await client.post(f"{API}/sessions")).status_code == 422


# --- session ids -------------------------------------------------------------------
async def test_unknown_session_is_404_on_every_route(client):
    unknown = "A" * 43
    for method, path in [
        ("post", "extract"),
        ("post", "analyze"),
        ("get", "job"),
        ("post", "job/stop"),
        ("get", "results"),
        ("get", "export.csv"),
    ]:
        response = await getattr(client, method)(f"{API}/sessions/{unknown}/{path}")
        assert response.status_code == 404, (method, path)
    put = await client.put(
        f"{API}/sessions/{unknown}/product",
        json={"product": {"name": "X", "aspects": ["a"]}},
    )
    assert put.status_code == 404


async def test_malformed_session_id_is_rejected_before_any_lookup(client):
    assert (await client.get(f"{API}/sessions/short/job")).status_code == 422
    assert (await client.get(f"{API}/sessions/{'a' * 20}%20x/job")).status_code == 422


# --- extract and confirm --------------------------------------------------------------
async def test_extract_returns_unconfirmed_product(client, llm):
    session_id = await upload(client)
    response = await client.post(f"{API}/sessions/{session_id}/extract")
    assert response.status_code == 200
    assert response.json()["product"] == llm.product.model_dump()
    async with client.db.session() as s:
        row = await s.get(AnalysisSession, session_id)
    assert row.product == llm.product.model_dump() and row.product_confirmed is False
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "Sample reviews:" in prompt and "Great battery life and a great screen" in prompt


async def test_extract_maps_llm_failures_to_http_errors(client, llm):
    session_id = await upload(client)
    llm.outage = True
    assert (await client.post(f"{API}/sessions/{session_id}/extract")).status_code == 503
    llm.outage = False
    llm.product = None  # the fake then returns an unparsable answer
    assert (await client.post(f"{API}/sessions/{session_id}/extract")).status_code == 502


async def test_confirm_normalizes_and_works_without_extract(client):
    session_id = await upload(client)
    response = await client.put(
        f"{API}/sessions/{session_id}/product",
        json={"product": {"name": "  Galaxy  S24 ", "aspects": ["Screen", "screen ", "Battery Life"]}},
    )
    assert response.status_code == 200
    assert response.json() == {
        "product": {"name": "Galaxy S24", "aspects": ["screen", "battery life"]},
        "confirmed": True,
    }


@pytest.mark.parametrize(
    "product",
    [
        {"name": "X", "aspects": []},
        {"name": "", "aspects": ["a"]},
        {"name": "X", "aspects": [f"a{i}" for i in range(11)]},
        {"name": "X", "aspects": ["a" * 41]},
    ],
)
async def test_confirm_validates_the_product(client, product):
    session_id = await upload(client)
    response = await client.put(
        f"{API}/sessions/{session_id}/product", json={"product": product}
    )
    assert response.status_code == 422


# --- analyze, job, results, export ------------------------------------------------------
async def test_full_flow(client, llm):
    session_id = await upload(client)
    assert (await client.post(f"{API}/sessions/{session_id}/extract")).status_code == 200
    await confirm(client, session_id)

    job = await analyze(client, session_id)
    assert job["status"] == "completed"
    assert (job["done"], job["total"], job["failed"], job["error"]) == (4, 4, 0, None)

    results = (await client.get(f"{API}/sessions/{session_id}/results")).json()
    assert results["product_name"] == "Galaxy S24"
    assert (results["review_count"], results["analyzed_count"], results["failed_count"]) == (4, 4, 0)
    battery, screen = results["aspects"]
    # review 1: great battery + great screen; 2: terrible screen; 4: battery
    assert battery["aspect"] == "Battery Life" and battery["mention_count"] == 2
    assert battery["mean_score"] == 3.0  # (5 + 1) / 2
    assert screen["aspect"] == "Screen" and screen["mention_count"] == 2
    assert screen["mean_score"] == 3.0
    assert screen["distribution"] == {"1": 1, "2": 0, "3": 0, "4": 0, "5": 1}

    export = await client.get(f"{API}/sessions/{session_id}/export.csv")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert 'filename="reviews-analysis-galaxy-s24.csv"' in export.headers["content-disposition"]
    assert export.headers["cache-control"] == "no-store"
    table = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
    assert table[0] == ["row", "text", "status", "Battery Life", "Screen"]
    assert table[1] == ["1", "Great battery life and a great screen", "done", "5", "5"]
    assert table[2] == ["2", "The screen is terrible", "done", "", "1"]
    assert table[3] == ["3", "Shipping was quick", "done", "", ""]
    assert table[4][1].startswith("'=HYPERLINK")  # formula neutralized
    assert table[4][3] == "1"


async def test_analysis_requires_confirmed_product(client):
    session_id = await upload(client)
    response = await client.post(f"{API}/sessions/{session_id}/analyze")
    assert response.status_code == 409
    await client.post(f"{API}/sessions/{session_id}/extract")  # extracted, not confirmed
    assert (await client.post(f"{API}/sessions/{session_id}/analyze")).status_code == 409


async def test_job_is_404_before_any_analysis(client):
    session_id = await upload(client)
    assert (await client.get(f"{API}/sessions/{session_id}/job")).status_code == 404


async def test_results_and_export_need_product_details(client):
    session_id = await upload(client)
    assert (await client.get(f"{API}/sessions/{session_id}/results")).status_code == 409
    assert (await client.get(f"{API}/sessions/{session_id}/export.csv")).status_code == 409


async def test_results_before_analysis_are_empty_not_an_error(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    results = (await client.get(f"{API}/sessions/{session_id}/results")).json()
    assert results["analyzed_count"] == 0
    assert all(a["mean_score"] is None for a in results["aspects"])


async def test_failed_reviews_are_reported(client):
    session_id = await upload(client, "text\nGreat battery life\nBAD battery review\n")
    await confirm(client, session_id)
    job = await analyze(client, session_id)
    assert (job["status"], job["done"], job["failed"]) == ("completed", 2, 1)
    results = (await client.get(f"{API}/sessions/{session_id}/results")).json()
    assert (results["analyzed_count"], results["failed_count"]) == (1, 1)
    table = list(csv.reader(io.StringIO(
        (await client.get(f"{API}/sessions/{session_id}/export.csv")).content.decode("utf-8-sig")
    )))
    assert [row[2] for row in table[1:]] == ["done", "failed"]


async def test_llm_outage_fails_the_job_cleanly(client, llm):
    session_id = await upload(client, "text\n" + "review\n" * 8)
    await confirm(client, session_id)
    llm.outage = True
    job = await analyze(client, session_id)
    assert job["status"] == "failed"
    assert job["error"] == "The language model server stopped responding"
    assert job["done"] < job["total"]


async def test_stopping_an_analysis_stops_calling_the_llm(client, llm):
    session_id = await upload(client, "text\n" + "great screen\n" * 20)
    await confirm(client, session_id)
    llm.gate = asyncio.Event()  # every LLM call hangs until released
    response = await client.post(f"{API}/sessions/{session_id}/analyze")
    assert response.status_code == 202
    while llm.inflight == 0:
        await asyncio.sleep(0)

    stopped = await client.post(f"{API}/sessions/{session_id}/job/stop")
    assert stopped.status_code == 200, stopped.text
    job = stopped.json()
    assert job["status"] == "failed"
    assert job["error"] == "You stopped the analysis."
    assert job["done"] < job["total"]
    assert llm.inflight == 0  # the requests in flight were aborted
    calls = len(llm.calls)

    llm.gate.set()
    await asyncio.sleep(0.05)
    assert len(llm.calls) == calls  # and no new ones were sent
    assert (await client.get(f"{API}/sessions/{session_id}/job")).json() == job

    llm.gate = None  # the session can be analyzed again
    assert (await analyze(client, session_id))["status"] == "completed"


async def test_stopping_when_nothing_runs_is_a_conflict(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    assert (await client.post(f"{API}/sessions/{session_id}/job/stop")).status_code == 409
    await analyze(client, session_id)  # finished: nothing left to stop
    assert (await client.post(f"{API}/sessions/{session_id}/job/stop")).status_code == 409


async def test_shutdown_interrupts_running_analyses(client, llm):
    session_id = await upload(client)
    await confirm(client, session_id)
    llm.gate = asyncio.Event()
    await client.post(f"{API}/sessions/{session_id}/analyze")
    while llm.inflight == 0:
        await asyncio.sleep(0)
    await main.app.state.analysis_tasks.shutdown()
    job = (await client.get(f"{API}/sessions/{session_id}/job")).json()
    assert (job["status"], job["error"]) == ("failed", "Interrupted")


async def _insert_active_job(client, session_id):
    async with client.db.session() as s:
        s.add(Job(session_id=session_id, status="running", total=1))


async def test_busy_session_rejects_conflicting_requests(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    await _insert_active_job(client, session_id)
    assert (await client.post(f"{API}/sessions/{session_id}/analyze")).status_code == 409
    assert (await client.post(f"{API}/sessions/{session_id}/extract")).status_code == 409
    put = await client.put(
        f"{API}/sessions/{session_id}/product",
        json={"product": {"name": "X", "aspects": ["a"]}},
    )
    assert put.status_code == 409


async def test_changing_the_product_discards_old_results(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    await analyze(client, session_id)

    await confirm(client, session_id, aspects=("screen", "price"))
    assert (await client.get(f"{API}/sessions/{session_id}/job")).status_code == 404
    results = (await client.get(f"{API}/sessions/{session_id}/results")).json()
    assert [a["aspect"] for a in results["aspects"]] == ["Screen", "Price"]
    assert results["analyzed_count"] == 0
    async with client.db.session() as s:
        assert await s.scalar(select(func.count()).select_from(Score)) == 0
        statuses = set((await s.scalars(select(Review.status))).all())
    assert statuses == {"pending"}


async def test_confirming_the_same_product_keeps_results(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    await analyze(client, session_id)
    await confirm(client, session_id)  # identical details
    assert (await client.get(f"{API}/sessions/{session_id}/job")).status_code == 200
    results = (await client.get(f"{API}/sessions/{session_id}/results")).json()
    assert results["analyzed_count"] == 4


async def test_reanalysis_starts_from_scratch(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    first = await analyze(client, session_id)
    second = await analyze(client, session_id)
    assert second["job_id"] != first["job_id"] and second["status"] == "completed"
    async with client.db.session() as s:
        assert await s.scalar(select(func.count()).select_from(Job)) == 1
        assert await s.scalar(select(func.count()).select_from(Score)) == 4  # not doubled


# --- cross-cutting -------------------------------------------------------------------------
async def test_sessions_are_isolated(client):
    a = await upload(client)
    b = await upload(client, "text\nGreat screen\n")
    await confirm(client, a)
    await analyze(client, a)
    assert (await client.get(f"{API}/sessions/{b}/job")).status_code == 404
    results_b = (await client.get(f"{API}/sessions/{b}/results"))
    assert results_b.status_code == 409  # b has no product at all


async def test_logs_never_contain_the_session_id(client):
    records: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Collect()
    app_logger.addHandler(handler)
    try:
        session_id = await upload(client)
        await client.get(f"{API}/sessions/{session_id}/job")
        await client.get(f"{API}/nonexistent")
    finally:
        app_logger.removeHandler(handler)
    assert not any(session_id in line for line in records)
    assert any("/sessions/{session_id}/job" in line for line in records)
    assert any("unmatched" in line for line in records)


async def test_rate_limit_applies_to_uploads(client):
    limiter.enabled = True
    limiter.reset()
    codes = [
        (await client.post(f"{API}/sessions", files=csv_file("text\nhello\n"))).status_code
        for _ in range(6)
    ]
    assert codes == [201] * 5 + [429]


async def test_cors_allows_the_dev_frontend(client):
    response = await client.options(
        f"{API}/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# --- session state (page reload) ----------------------------------------------------------
async def _state(client, session_id) -> dict:
    response = await client.get(f"{API}/sessions/{session_id}")
    assert response.status_code == 200, response.text
    return response.json()


async def test_session_state_follows_the_flow(client, llm):
    created = (await client.post(f"{API}/sessions", files=csv_file())).json()
    session_id = created["session_id"]

    state = await _state(client, session_id)
    assert state == {
        "filename": "reviews.csv",
        "review_count": 4,
        "top_ngrams": created["top_ngrams"],
        "product": None,
        "product_confirmed": False,
        "job": None,
    }

    await client.post(f"{API}/sessions/{session_id}/extract")
    state = await _state(client, session_id)
    assert state["product"] == llm.product.model_dump()
    assert state["product_confirmed"] is False

    await confirm(client, session_id)
    state = await _state(client, session_id)
    assert state["product_confirmed"] is True
    assert state["job"] is None

    await analyze(client, session_id)
    state = await _state(client, session_id)
    assert state["job"]["status"] == "completed"
    assert (state["job"]["done"], state["job"]["total"]) == (4, 4)


async def test_session_state_shows_a_running_job(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    await _insert_active_job(client, session_id)
    state = await _state(client, session_id)
    assert state["job"]["status"] == "running"


async def test_session_state_forgets_the_job_when_the_product_changes(client):
    session_id = await upload(client)
    await confirm(client, session_id)
    await analyze(client, session_id)
    await confirm(client, session_id, aspects=("screen", "price"))
    state = await _state(client, session_id)
    assert state["job"] is None
    assert state["product"]["aspects"] == ["screen", "price"]
    assert state["product_confirmed"] is True


async def test_session_state_does_not_repeat_the_access_token(client):
    session_id = await upload(client)
    response = await client.get(f"{API}/sessions/{session_id}")
    assert session_id not in response.text


async def test_session_state_of_an_unknown_or_malformed_session(client):
    assert (await client.get(f"{API}/sessions/{'A' * 43}")).status_code == 404
    assert (await client.get(f"{API}/sessions/short")).status_code == 422
