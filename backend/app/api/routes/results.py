import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.aggregate import ExportRow, build_export_csv, build_results
from app.ai import ProductDetails
from app.api.deps import DbDep, SessionId, SessionRequired
from app.core.config import get_settings
from app.core.limiter import limiter
from app.database.models import AnalysisSession, Review, ReviewStatus, Score
from app.models import ResultsResponse

router = APIRouter()
settings = get_settings()


async def _load_product(db: DbDep, session_id: str) -> ProductDetails:
    async with db.session() as s:
        row = await s.get(AnalysisSession, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
    if row.product is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No product details yet")
    return ProductDetails.model_validate(row.product)


@router.get(
    "/sessions/{session_id}/results",
    response_model=ResultsResponse,
    dependencies=[SessionRequired],
)
@limiter.limit(settings.rate_limit.read_rate_limit)
async def get_results(request: Request, session_id: SessionId, db: DbDep) -> ResultsResponse:
    product = await _load_product(db, session_id)
    async with db.session() as s:
        status_counts = dict(
            (
                await s.execute(
                    select(Review.status, func.count()).where(Review.session_id == session_id).group_by(Review.status)
                )
            ).all()
        )
        scores = [
            (aspect, score)
            for aspect, score in (
                await s.execute(select(Score.aspect, Score.score).where(Score.session_id == session_id))
            ).all()
        ]
    return build_results(
        product,
        review_count=sum(status_counts.values()),
        analyzed_count=status_counts.get(ReviewStatus.DONE.value, 0),
        failed_count=status_counts.get(ReviewStatus.FAILED.value, 0),
        scores=scores,
    )


@router.get("/sessions/{session_id}/export.csv", dependencies=[SessionRequired])
@limiter.limit(settings.rate_limit.read_rate_limit)
async def export_csv(request: Request, session_id: SessionId, db: DbDep) -> Response:
    product = await _load_product(db, session_id)
    async with db.session() as s:
        reviews = (
            await s.execute(
                select(Review.id, Review.row_index, Review.text, Review.status).where(Review.session_id == session_id)
            )
        ).all()
        score_rows = (
            await s.execute(select(Score.review_id, Score.aspect, Score.score).where(Score.session_id == session_id))
        ).all()

    rows = {
        review_id: ExportRow(row_index=row_index, text=text, status=review_status)
        for review_id, row_index, text, review_status in reviews
    }
    for review_id, aspect, score in score_rows:
        rows[review_id].scores[aspect] = score

    slug = re.sub(r"[^a-z0-9]+", "-", product.name.lower()).strip("-") or "product"
    return Response(
        content=build_export_csv(product, list(rows.values())),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reviews-analysis-{slug}.csv"',
            "Cache-Control": "no-store",
        },
    )
