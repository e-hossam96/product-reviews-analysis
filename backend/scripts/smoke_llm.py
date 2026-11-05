"""Manual check of the AI layer against a running llama-server.

uv run --directory backend --env-file ../.env python -m scripts.smoke_llm \
    data/sample_reviews.csv --base-url http://localhost:8000/v1 --limit 30 \
    --aspects "battery life,sound quality,comfort,noise cancellation,price,bluetooth connection,microphone,build quality"
"""

import argparse
import asyncio
import csv
import sys
import time
from collections import Counter
from pathlib import Path

from app.ai import (
    LLMOutputError,
    LLMParams,
    ProductDetails,
    extract_product_details,
    score_review,
)
from app.core.config import get_settings
from app.ingest import parse_reviews, sample_reviews
from app.ngrams import top_ngrams
from openai import AsyncOpenAI


def load_expected(path: Path) -> dict[int, dict[str, str]] | None:
    """Ground truth from the generated sample file's `expected` column."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "expected" not in reader.fieldnames:
            return None
        expected: dict[int, dict[str, str]] = {}
        for i, row in enumerate(reader):  # matches ingest row_index for gap-free files
            pairs = [p.split(":") for p in (row["expected"] or "").split("|") if p]
            expected[i] = {aspect: polarity for aspect, polarity in pairs}
        return expected


def polarity(score: int) -> str:
    return "pos" if score >= 4 else "neg" if score <= 2 else "neu"


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    cfg, analysis = settings.openai, settings.analysis

    client = AsyncOpenAI(
        api_key=cfg.api_key.get_secret_value(),
        base_url=args.base_url or cfg.api_base,
        timeout=cfg.timeout_seconds,
        max_retries=cfg.max_retries,
    )
    params = LLMParams(
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_completion_tokens,
        seed=cfg.seed,
    )

    csv_path = Path(args.csv)
    parsed = parse_reviews(
        csv_path.read_bytes(),
        max_rows=10_000,  # dev tool: not bound by the product's SESSION_MAX_ROWS
        max_bytes=settings.session.max_upload_mb * 1024 * 1024,
    )
    texts = [r.text for r in parsed.reviews]
    grams = top_ngrams(texts, max_n=analysis.ngram_max_n, top_k=analysis.ngram_top_k)
    samples = sample_reviews(
        texts,
        k=analysis.extraction_sample_size,
        max_chars=analysis.extraction_sample_chars,
    )
    print(f"{len(texts)} reviews, {len(grams)} n-grams, {len(samples)} sampled\n")

    started = time.perf_counter()
    product = await extract_product_details(
        client,
        params,
        ngrams=[(g.ngram, g.count) for g in grams],
        sample_reviews=samples,
        retries=analysis.scoring_retries,
    )
    print(f"EXTRACT ({time.perf_counter() - started:.1f}s):")
    print(product.model_dump_json(indent=2), "\n")

    if args.aspects:
        product = ProductDetails(name=product.name, aspects=args.aspects.split(","))
        print(f"aspects overridden: {product.aspects}\n")

    semaphore = asyncio.Semaphore(settings.performance.openai_concurrent_requests)

    async def score(text: str):
        async with semaphore:
            try:
                return await score_review(
                    client,
                    params,
                    product=product,
                    review_text=text,
                    max_chars=analysis.review_max_chars,
                    retries=analysis.scoring_retries,
                )
            except LLMOutputError as e:
                return e

    batch = parsed.reviews[: args.limit]
    started = time.perf_counter()
    results = await asyncio.gather(*(score(r.text) for r in batch))
    elapsed = time.perf_counter() - started

    expected = load_expected(csv_path)
    stats: Counter[str] = Counter()
    failures = 0
    for review, result in zip(batch, results):
        print(f"[{review.row_index}] {review.text[:90]}")
        want = expected.get(review.row_index, {}) if expected else {}
        if want:
            print("    expected:", ", ".join(f"{a}:{p}" for a, p in want.items()))
        if isinstance(result, Exception):
            failures += 1
            print(f"    FAILED: {result}")
            continue
        got = {m.aspect: polarity(m.score) for m in result.mentions}
        if not result.mentions:
            print("    (no aspects mentioned)")
        for m in result.mentions:
            print(f"    got: {m.aspect}: {m.score} ({polarity(m.score)})")
        if expected:
            stats["expected"] += len(want)
            stats["found"] += sum(a in got for a in want)
            stats["polarity_ok"] += sum(got.get(a) == p for a, p in want.items())
            stats["extra"] += sum(a not in want for a in got)

    print(f"\nSCORE: {len(batch)} reviews in {elapsed:.1f}s ({elapsed / len(batch):.2f}s/review), {failures} failed")
    if expected and stats["expected"]:
        print(
            f"ACCURACY: found {stats['found']}/{stats['expected']} expected aspects "
            f"({stats['found'] / stats['expected']:.0%}), "
            f"polarity correct {stats['polarity_ok']}/{stats['found'] or 1} "
            f"({stats['polarity_ok'] / (stats['found'] or 1):.0%}), "
            f"extra aspects reported: {stats['extra']}"
        )
    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--base-url", help="override OPENAI_API_BASE")
    parser.add_argument("--aspects", help="comma-separated aspects, replaces the extracted list")
    parser.add_argument("--limit", type=int, default=20)
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run(parser.parse_args()))
