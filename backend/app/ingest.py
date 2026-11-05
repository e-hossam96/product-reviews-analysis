import csv
import html
import io
import random
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

TEXT_COLUMN = "text"
_DELIMITERS = ",;\t|"
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")  # requires a letter, so "<5" survives
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0e-\x1b\x7f]")


class IngestError(ValueError):
    """The uploaded file can't be used. The message is safe to show to the user."""


@dataclass(frozen=True, slots=True)
class ParsedReview:
    row_index: int  # 0-based position among the CSV's data rows
    text: str


@dataclass(frozen=True, slots=True)
class ParseResult:
    reviews: list[ParsedReview]
    total_rows: int
    skipped_empty: int


def clean_text(raw: str) -> str:
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_RE.sub("", text)
    return " ".join(text.split())


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")  # also strips an Excel BOM
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def parse_reviews(data: bytes, *, max_rows: int, max_bytes: int) -> ParseResult:
    if len(data) > max_bytes:
        raise IngestError(f"The file is larger than the {max_bytes / 1024 / 1024:g} MB limit")
    if not data.strip():
        raise IngestError("The file is empty")

    content = _decode(data)
    first_line = content.split("\n", 1)[0]
    delimiter = max(_DELIMITERS, key=first_line.count)  # "," when none is present

    reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as e:
        raise IngestError("Could not read the CSV header") from e

    names = [h.strip().lower() for h in header]
    if TEXT_COLUMN not in names:
        found = ", ".join(h.strip() for h in header if h.strip()) or "none"
        raise IngestError(f"Missing required column 'text'. Found columns: {found}")
    text_idx = names.index(TEXT_COLUMN)

    reviews: list[ParsedReview] = []
    total = 0
    skipped = 0
    try:
        for row in reader:
            if not row:  # fully blank line
                continue
            total += 1
            if total > max_rows:
                raise IngestError(f"The file has more than {max_rows} rows")
            raw = row[text_idx] if text_idx < len(row) else ""
            text = clean_text(raw)
            if text:
                reviews.append(ParsedReview(row_index=total - 1, text=text))
            else:
                skipped += 1
    except csv.Error as e:
        raise IngestError(f"Malformed CSV near data row {total + 1}: {e}") from e

    if not reviews:
        raise IngestError("No non-empty reviews found in the 'text' column")
    return ParseResult(reviews=reviews, total_rows=total, skipped_empty=skipped)


def sample_reviews(
    texts: Sequence[str],
    *,
    k: int,
    max_chars: int,
    min_chars: int = 20,
    seed: int = 42,
) -> list[str]:
    """Deterministic sample for the extraction prompt, truncated to max_chars."""
    pool = [t for t in texts if len(t) >= min_chars] or list(texts)
    chosen = random.Random(seed).sample(pool, min(k, len(pool)))
    return [t[:max_chars].rstrip() for t in chosen]
