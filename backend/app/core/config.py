from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _config(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(env_file=None, env_prefix=prefix, extra="ignore")


class ApplicationSettings(BaseSettings):
    model_config = _config("application_")
    name: str = "reviews-analysis"
    version: str = "0.1.0"
    log_level: str = "INFO"


class OpenAISettings(BaseSettings):
    """OpenAI-compatible client pointed at llama-server."""

    model_config = _config("openai_")
    api_key: SecretStr = SecretStr("not-needed")
    api_base: str = "http://localhost:8000/v1"
    model_name: str = "local"
    temperature: float = 0.0
    max_completion_tokens: int = 1024
    seed: int = 42
    timeout_seconds: float = 120.0
    max_retries: int = 2


class PerformanceSettings(BaseSettings):
    model_config = _config("performance_")
    # keep equal to llama-server's --parallel
    openai_concurrent_requests: int = Field(default=4, ge=1)


class RateLimitSettings(BaseSettings):
    model_config = _config("rate_limit_")
    upload: int = 5
    extract: int = 10
    analyze: int = 5
    read: int = 120  # job polling, results, export
    health: int = 60

    @property
    def upload_rate_limit(self) -> str:
        return f"{self.upload}/minute"

    @property
    def extract_rate_limit(self) -> str:
        return f"{self.extract}/minute"

    @property
    def analyze_rate_limit(self) -> str:
        return f"{self.analyze}/minute"

    @property
    def read_rate_limit(self) -> str:
        return f"{self.read}/minute"

    @property
    def health_rate_limit(self) -> str:
        return f"{self.health}/minute"


class CORSSettings(BaseSettings):
    model_config = _config("cors_")
    allowed_origins: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5173",  # Vite dev server
    ]
    allowed_methods: list[str] = ["GET", "POST", "PUT"]
    allowed_headers: list[str] = ["*"]
    allow_credentials: bool = True


class DatabaseSettings(BaseSettings):
    model_config = _config("database_")
    path: str = "./data/reviews-analysis-database.db"

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.path}"


class LangfuseSettings(BaseSettings):
    """Langfuse Cloud. Tracing is simply off when the keys are absent."""

    model_config = _config("langfuse_")
    public_key: str | None = None
    secret_key: SecretStr | None = None
    host: str = "https://cloud.langfuse.com"

    @property
    def enabled(self) -> bool:
        return bool(self.public_key and self.secret_key)


class SessionSettings(BaseSettings):
    model_config = _config("session_")
    ttl_hours: int = Field(default=6, ge=1)
    max_upload_mb: int = Field(default=10, ge=1)
    max_rows: int = Field(default=100, ge=1)
    cleanup_interval_minutes: int = Field(default=30, ge=1)


class AnalysisSettings(BaseSettings):
    model_config = _config("analysis_")
    review_max_chars: int = 1000  # reviews are truncated to this before scoring
    ngram_max_n: int = Field(default=3, ge=1, le=3)
    ngram_top_k: int = 100
    # The extraction call must fit in ONE llama-server slot
    # (ctx-size / parallel tokens), so keep the sample small.
    extraction_sample_size: int = 20
    extraction_sample_chars: int = 300
    scoring_retries: int = 1
    estimated_seconds_per_review: float = 2.5


class Settings(BaseModel):
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
