import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.ai.schemas import MAX_SCORE, MIN_SCORE, ProductDetails
from app.models import AspectResult, ResultsResponse

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def build_results(
    product: ProductDetails,
    *,
    review_count: int,
    analyzed_count: int,
    failed_count: int,
    scores: Iterable[tuple[str, int]],
) -> ResultsResponse:
    """Per-aspect mean and score distribution, in the product's aspect order."""
    by_aspect: dict[str, list[int]] = defaultdict(list)
    for aspect, score in scores:
        by_aspect[aspect].append(score)

    aspects: list[AspectResult] = []
    for aspect in product.aspects:
        values = by_aspect.get(aspect, [])
        distribution = {s: 0 for s in range(MIN_SCORE, MAX_SCORE + 1)}
        for value in values:
            distribution[value] += 1
        aspects.append(
            AspectResult(
                aspect=aspect,
                mean_score=round(sum(values) / len(values), 2) if values else None,
                mention_count=len(values),
                distribution=distribution,
            )
        )
    return ResultsResponse(
        product_name=product.name,
        review_count=review_count,
        analyzed_count=analyzed_count,
        failed_count=failed_count,
        aspects=aspects,
    )


@dataclass(slots=True)
class ExportRow:
    row_index: int
    text: str
    status: str
    scores: dict[str, int] = field(default_factory=dict)


def csv_safe(value: str) -> str:
    """Stop spreadsheet apps from running a cell that starts like a formula."""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def build_export_csv(product: ProductDetails, rows: Sequence[ExportRow]) -> bytes:
    """UTF-8 with a BOM, so Excel shows non-ASCII text correctly."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "text", "status", *(csv_safe(a) for a in product.aspects)])
    for row in sorted(rows, key=lambda r: r.row_index):
        writer.writerow(
            [
                row.row_index + 1,
                csv_safe(row.text),
                row.status,
                *(row.scores.get(a, "") for a in product.aspects),
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
