from enum import StrEnum

from pydantic import BaseModel, Field

from app.ai.schemas import ProductDetails


class HealthCheckResponse(BaseModel):
    status: str = "ok"
    application_name: str
    application_version: str


class ConfigResponse(BaseModel):
    max_rows: int
    max_upload_mb: int
    max_aspects: int
    estimated_seconds_per_review: float
    tracing_enabled: bool


# --- step 1: upload ---------------------------------------------------------
class NgramCount(BaseModel):
    ngram: str
    count: int = Field(ge=1)


class SessionCreateResponse(BaseModel):
    session_id: str
    review_count: int
    skipped_empty: int
    top_ngrams: list[NgramCount]


# --- steps 2-3: extract and confirm ------------------------------------------
class ExtractResponse(BaseModel):
    product: ProductDetails


class ConfirmProductRequest(BaseModel):
    product: ProductDetails


class ConfirmProductResponse(BaseModel):
    product: ProductDetails
    confirmed: bool = True


# --- steps 4-5: analysis job ---------------------------------------------------
class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    done: int = Field(ge=0)
    total: int = Field(ge=0)
    failed: int = Field(ge=0)
    error: str | None = None


class SessionStateResponse(BaseModel):
    """Where a session stands, so a reloaded page can pick up where it left off."""

    filename: str | None
    review_count: int
    top_ngrams: list[NgramCount]
    product: ProductDetails | None
    product_confirmed: bool
    job: JobStatusResponse | None  # the latest analysis, if one was started


# --- step 6: results -----------------------------------------------------------
class AspectResult(BaseModel):
    aspect: str
    mean_score: float | None
    mention_count: int = Field(ge=0)
    distribution: dict[int, int]


class ResultsResponse(BaseModel):
    product_name: str
    review_count: int
    analyzed_count: int
    failed_count: int
    aspects: list[AspectResult]
