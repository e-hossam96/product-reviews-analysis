import pytest
from app.ai.schemas import (
    MAX_ASPECTS,
    ProductDetails,
    ReviewScores,
    build_review_scores_model,
)
from pydantic import ValidationError


def test_product_details_normalizes_and_dedupes():
    p = ProductDetails(
        name="  Galaxy   S24 ",
        aspects=["Battery  Life", "battery life", " Screen ", ""],
    )
    assert p.name == "Galaxy S24"
    assert p.aspects == ["battery life", "screen"]


def test_product_details_requires_at_least_one_aspect():
    with pytest.raises(ValidationError):
        ProductDetails(name="X", aspects=["   "])


def test_product_details_caps_aspect_count():
    with pytest.raises(ValidationError):
        ProductDetails(name="X", aspects=[f"a{i}" for i in range(MAX_ASPECTS + 1)])


def test_review_scores_allows_empty_mentions():
    assert ReviewScores(mentions=[]).mentions == []


def test_review_scores_rejects_out_of_range_score():
    for bad in (0, 6):
        with pytest.raises(ValidationError):
            ReviewScores(mentions=[{"aspect": "screen", "score": bad}])


def test_review_scores_keeps_first_mention_per_aspect():
    r = ReviewScores(
        mentions=[
            {"aspect": "screen", "score": 5},
            {"aspect": "screen", "score": 1},
        ]
    )
    assert [(m.aspect, m.score) for m in r.mentions] == [("screen", 5)]


def test_strict_model_rejects_unknown_aspect():
    model = build_review_scores_model(["battery life", "screen"])
    ok = model.model_validate({"mentions": [{"aspect": "screen", "score": 4}]})
    assert ok.mentions[0].aspect == "screen"
    with pytest.raises(ValidationError):
        model.model_validate({"mentions": [{"aspect": "price", "score": 4}]})


def test_strict_model_schema_has_enum_and_is_cached():
    aspects = ["battery life", "screen"]
    model = build_review_scores_model(aspects)
    assert model is build_review_scores_model(list(aspects))

    schema = model.model_json_schema()
    aspect_prop = schema["$defs"]["AspectMentionStrict"]["properties"]["aspect"]
    assert aspect_prop["enum"] == aspects
    assert schema["properties"]["mentions"]["maxItems"] == len(aspects)


def test_strict_model_requires_aspects():
    with pytest.raises(ValueError):
        build_review_scores_model([])
