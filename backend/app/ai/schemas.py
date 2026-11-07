from functools import cache
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    create_model,
    field_validator,
    model_validator,
)

MAX_ASPECTS = 10
MAX_ASPECT_LENGTH = 40
MIN_SCORE = 1
MAX_SCORE = 5

Aspect = Annotated[str, StringConstraints(min_length=1, max_length=MAX_ASPECT_LENGTH)]


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


class ProductDetails(BaseModel):
    """The single product of an uploaded CSV, as extracted and then confirmed."""

    name: str = Field(min_length=1, max_length=100)
    aspects: list[Aspect] = Field(min_length=1, max_length=MAX_ASPECTS)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: Any) -> Any:
        return _collapse_whitespace(value) if isinstance(value, str) else value

    @field_validator("aspects", mode="before")
    @classmethod
    def _clean_aspects(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        seen: dict[str, None] = {}  # insertion-ordered de-duplication
        for item in value:
            if not isinstance(item, str):
                return value  # let normal validation raise the type error
            cleaned = _collapse_whitespace(item).lower()
            if cleaned:
                seen.setdefault(cleaned)
        return list(seen)


class AspectMention(BaseModel):
    """One aspect that a review actually talks about."""

    aspect: str
    score: int = Field(ge=MIN_SCORE, le=MAX_SCORE)


class ReviewScores(BaseModel):
    """LLM output for one review. An empty list means no aspect is mentioned."""

    mentions: list[AspectMention]

    @model_validator(mode="after")
    def _keep_first_mention_per_aspect(self) -> ReviewScores:
        seen: set[str] = set()
        unique: list[AspectMention] = []
        for mention in self.mentions:
            if mention.aspect not in seen:
                seen.add(mention.aspect)
                unique.append(mention)
        self.mentions = unique
        return self


@cache
def _build_strict_model(aspects: tuple[str, ...]) -> type[ReviewScores]:
    aspect_enum = Literal[aspects]  # type: ignore[valid-type]
    mention = create_model("AspectMentionStrict", __base__=AspectMention, aspect=(aspect_enum, ...))
    return create_model(
        "ReviewScoresStrict",
        __base__=ReviewScores,
        mentions=(list[mention], Field(max_length=len(aspects))),  # type: ignore[valid-type]
    )


def build_review_scores_model(aspects: list[str]) -> type[ReviewScores]:
    """ReviewScores whose `aspect` field is an enum of the confirmed aspects.

    Pass the result to `chat.completions.parse(response_format=...)` so the
    model cannot invent aspects. Cached per aspect list.
    """
    if not aspects:
        raise ValueError("aspects must not be empty")
    return _build_strict_model(tuple(aspects))
