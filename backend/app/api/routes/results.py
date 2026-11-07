import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.aggregate import ExportRow, build_export_csv, build_results
from app.ai import ProductDetails
from app.api.deps import DbDep, SessionDep, SessionId
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.models import AnalysisSession, Review, ReviewStatus, Score
from app.models import ResultsResponse

router = APIRouter()
settings = get_settings()


def _product_of(session: AnalysisSession) -> ProductDetails:
    if session.product is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No product details yet")
    return ProductDetails.model_validate(session.product)


def _filename_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "product"


@router.get("/sessions/{session_id}/results", response_model=ResultsResponse)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def get_results(
    request: Request, session_id: SessionId, session: SessionDep, db: DbDep
) -> ResultsResponse:
    product = _product_of(session)
    async with db.session() as s:
        status_counts = await s.execute(
            select(Review.status, func.count())
            .where(Review.session_id == session_id)
            .group_by(Review.status)
        )
        reviews_by_status: dict[str, int] = dict(status_counts.all())
        scores = await s.execute(
            select(Score.aspect, Score.score).where(Score.session_id == session_id)
        )
        aspect_scores = [(aspect, score) for aspect, score in scores]

    return build_results(
        product,
        review_count=sum(reviews_by_status.values()),
        analyzed_count=reviews_by_status.get(ReviewStatus.DONE.value, 0),
        failed_count=reviews_by_status.get(ReviewStatus.FAILED.value, 0),
        scores=aspect_scores,
    )


@router.get("/sessions/{session_id}/export.csv")
@limiter.limit(settings.rate_limit.read_rate_limit)
async def export_csv(
    request: Request, session_id: SessionId, session: SessionDep, db: DbDep
) -> Response:
    product = _product_of(session)
    async with db.session() as s:
        reviews = await s.execute(
            select(Review.id, Review.row_index, Review.text, Review.status).where(
                Review.session_id == session_id
            )
        )
        rows = {
            review_id: ExportRow(row_index=row_index, text=text, status=review_status)
            for review_id, row_index, text, review_status in reviews
        }
        scores = await s.execute(
            select(Score.review_id, Score.aspect, Score.score).where(Score.session_id == session_id)
        )
        for review_id, aspect, score in scores:
            rows[review_id].scores[aspect] = score

    filename = f"reviews-analysis-{_filename_slug(product.name)}.csv"
    return Response(
        content=build_export_csv(product, list(rows.values())),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
