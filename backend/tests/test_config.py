from app.core.config import Settings


def test_defaults_load_without_env():
    s = Settings()
    assert s.openai.temperature == 0.0
    assert s.session.ttl_hours == 6
    assert s.database.database_url.startswith("sqlite+aiosqlite:///")


def test_langfuse_enabled_only_with_both_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert Settings().langfuse.enabled is False

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    assert Settings().langfuse.enabled is False

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    assert Settings().langfuse.enabled is True


def test_secrets_are_not_leaked_in_repr(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-value")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "another-secret")
    text = repr(Settings())
    assert "super-secret-value" not in text
    assert "another-secret" not in text


def test_env_overrides_and_rate_limit_format(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOAD", "7")
    monkeypatch.setenv("PERFORMANCE_OPENAI_CONCURRENT_REQUESTS", "2")
    s = Settings()
    assert s.rate_limit.upload_rate_limit == "7/minute"
    assert s.performance.openai_concurrent_requests == 2


def test_cors_origins_parse_from_json_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://example.test"]')
    assert Settings().cors.allowed_origins == ["http://example.test"]


def test_default_row_limit(monkeypatch):
    monkeypatch.delenv("SESSION_MAX_ROWS", raising=False)
    assert Settings().session.max_rows == 100
