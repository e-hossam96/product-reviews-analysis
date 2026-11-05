import logging
from dataclasses import dataclass
from typing import Any, TypeVar

from openai import AsyncOpenAI, LengthFinishReasonError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRY_TEMPERATURE = 0.3


class LLMOutputError(RuntimeError):
    """The model never produced valid structured output within the retry budget."""


@dataclass(frozen=True, slots=True)
class LLMParams:
    model: str
    temperature: float = 0.0
    max_completion_tokens: int = 1024
    seed: int = 42


async def parse_structured[T: BaseModel](
    client: AsyncOpenAI,
    params: LLMParams,
    *,
    system: str,
    user: str,
    response_format: type[T],
    retries: int = 1,
    request_kwargs: dict[str, Any] | None = None,
) -> T:
    """One schema-constrained chat call; invalid output is retried, outages are not."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        # temperature 0 + the same seed would just repeat the same bad answer
        temperature = params.temperature if attempt == 0 else max(params.temperature, RETRY_TEMPERATURE)
        try:
            completion = await client.chat.completions.parse(
                model=params.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=response_format,
                temperature=temperature,
                max_tokens=params.max_completion_tokens,
                seed=params.seed + attempt,
                **(request_kwargs or {}),
            )
        except (ValidationError, LengthFinishReasonError) as e:
            last_error = e
            logger.warning("Invalid LLM output (attempt %d): %s", attempt + 1, e)
            continue

        message = completion.choices[0].message
        if message.parsed is not None:
            return message.parsed
        last_error = ValueError(message.refusal or "empty response")
        logger.warning("No parsed LLM output (attempt %d): %s", attempt + 1, last_error)

    raise LLMOutputError(f"No valid output after {retries + 1} attempt(s): {last_error}") from last_error
