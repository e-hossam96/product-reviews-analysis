import hashlib
from contextlib import nullcontext

import langfuse

from app import tracing

SECRET = "super-secret-session-token"


def test_disabled_tracing_is_a_no_op(monkeypatch):
    monkeypatch.setattr(tracing, "tracing_enabled", lambda: False)
    assert tracing.call_kwargs("score") == {}
    with tracing.trace_session(SECRET, "score"):
        pass


def test_enabled_tracing_names_the_call(monkeypatch):
    monkeypatch.setattr(tracing, "tracing_enabled", lambda: True)
    assert tracing.call_kwargs("extract") == {"name": "extract"}


def test_trace_session_passes_a_hash_never_the_token(monkeypatch):
    seen: list[dict] = []

    def fake_propagate(**kwargs):
        seen.append(kwargs)
        return nullcontext()

    monkeypatch.setattr(tracing, "tracing_enabled", lambda: True)
    monkeypatch.setattr(langfuse, "propagate_attributes", fake_propagate)
    with tracing.trace_session(SECRET, "score"):
        pass

    expected = hashlib.sha256(SECRET.encode()).hexdigest()[:16]
    assert seen == [{"session_id": expected, "tags": ["score"]}]
    assert SECRET not in str(seen)


def test_settings_enable_tracing_only_with_both_keys(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    assert Settings().langfuse.enabled is False
