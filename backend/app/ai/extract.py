from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.ai.llm import LLMParams, parse_structured
from app.ai.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_prompt
from app.ai.schemas import ProductDetails


async def extract_product_details(
    client: AsyncOpenAI,
    params: LLMParams,
    *,
    ngrams: Sequence[tuple[str, int]],
    sample_reviews: Sequence[str],
    max_ngrams: int = 40,
    retries: int = 1,
    request_kwargs: dict[str, Any] | None = None,
) -> ProductDetails:
    if not sample_reviews:
        raise ValueError("sample_reviews must not be empty")
    return await parse_structured(
        client,
        params,
        system=EXTRACTION_SYSTEM_PROMPT,
        user=build_extraction_user_prompt(ngrams, sample_reviews, max_ngrams),
        response_format=ProductDetails,
        retries=retries,
        request_kwargs=request_kwargs,
    )
