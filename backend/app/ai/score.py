from typing import Any

from openai import AsyncOpenAI

from app.ai.llm import LLMParams, parse_structured
from app.ai.prompts import build_scoring_system_prompt, build_scoring_user_prompt
from app.ai.schemas import ProductDetails, ReviewScores, build_review_scores_model


async def score_review(
    client: AsyncOpenAI,
    params: LLMParams,
    *,
    product: ProductDetails,
    review_text: str,
    max_chars: int = 1000,
    retries: int = 1,
    request_kwargs: dict[str, Any] | None = None,
) -> ReviewScores:
    """Aspects mentioned in one review. An empty `mentions` list is a valid answer."""
    return await parse_structured(
        client,
        params,
        system=build_scoring_system_prompt(product),
        user=build_scoring_user_prompt(review_text, max_chars),
        response_format=build_review_scores_model(product.aspects),
        retries=retries,
        request_kwargs=request_kwargs,
    )
