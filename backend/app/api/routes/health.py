from fastapi import APIRouter, Request

from app.ai.schemas import MAX_ASPECTS
from app.core.config import get_settings
from app.core.limiter import limiter
from app.models import ConfigResponse, HealthCheckResponse

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthCheckResponse)
@limiter.limit(settings.rate_limit.health_rate_limit)
async def health_check(request: Request) -> HealthCheckResponse:
    return HealthCheckResponse(
        application_name=settings.application.name,
        application_version=settings.application.version,
    )


@router.get("/config", response_model=ConfigResponse)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def get_app_config(request: Request) -> ConfigResponse:
    """Limits the upload page shows before the user picks a file."""
    return ConfigResponse(
        max_rows=settings.session.max_rows,
        max_upload_mb=settings.session.max_upload_mb,
        max_aspects=MAX_ASPECTS,
        estimated_seconds_per_review=settings.analysis.estimated_seconds_per_review,
        tracing_enabled=settings.langfuse.enabled,
    )
