"""The real OpenAI SDK against a mock transport: what actually goes over the wire."""

import json

import httpx
import openai
import pytest
from openai import AsyncOpenAI

from app.ai import (
    LLMOutputError,
    LLMParams,
    ProductDetails,
    extract_product_details,
    score_review,
)

PRODUCT = ProductDetails(name="Galaxy S24", aspects=["battery life", "screen"])
PARAMS = LLMParams(model="local", temperature=0.0, max_completion_tokens=256, seed=42)


def completion(content: str) -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "local",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def make_client(*responses):
    """Each response is a content string, an int status code, or an exception."""
    sent: list[dict] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, int):
            return httpx.Response(item, json={"error": {"message": "nope"}})
        return httpx.Response(200, json=completion(item))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenAI(
        api_key="x", base_url="http://llm.test/v1", http_client=http, max_retries=0
    )
    return client, sent


async def test_score_request_shape_and_parsed_result():
    client, sent = make_client('{"mentions": [{"aspect": "screen", "score": 4}]}')
    result = await score_review(client, PARAMS, product=PRODUCT, review_text="Nice screen")

    assert [(m.aspect, m.score) for m in result.mentions] == [("screen", 4)]
    body = sent[0]
    assert (body["max_tokens"], body["seed"], body["temperature"]) == (256, 42, 0.0)
    assert body["model"] == "local"
    schema = body["response_format"]["json_schema"]["schema"]
    aspect = schema["$defs"]["AspectMentionStrict"]["properties"]["aspect"]
    assert aspect["enum"] == ["battery life", "screen"]
    assert body["messages"][0]["role"] == "system"
    assert "<review>\nNice screen\n</review>" in body["messages"][1]["content"]


async def test_extract_request_uses_the_product_schema():
    client, sent = make_client('{"name": "Galaxy S24", "aspects": ["Screen"]}')
    product = await extract_product_details(
        client, PARAMS, ngrams=[("screen", 3)], sample_reviews=["Nice screen"]
    )
    assert product.model_dump() == {"name": "Galaxy S24", "aspects": ["screen"]}
    assert sent[0]["response_format"]["json_schema"]["name"] == "ProductDetails"


async def test_unparsable_json_is_retried_with_a_new_seed_and_temperature():
    client, sent = make_client(
        "this is not json", '{"mentions": [{"aspect": "screen", "score": 5}]}'
    )
    result = await score_review(
        client, PARAMS, product=PRODUCT, review_text="Nice screen", retries=1
    )
    assert result.mentions[0].score == 5
    assert [b["seed"] for b in sent] == [42, 43]
    assert sent[0]["temperature"] == 0.0 and sent[1]["temperature"] > 0.0


async def test_output_that_breaks_the_schema_is_rejected():
    client, _ = make_client(
        '{"mentions": [{"aspect": "price", "score": 4}]}',  # not in the enum
        '{"mentions": [{"aspect": "screen", "score": 9}]}',  # out of range
    )
    with pytest.raises(LLMOutputError):
        await score_review(client, PARAMS, product=PRODUCT, review_text="x", retries=1)


async def test_connection_errors_surface_unchanged():
    client, sent = make_client(httpx.ConnectError("refused"))
    with pytest.raises(openai.APIConnectionError):
        await score_review(client, PARAMS, product=PRODUCT, review_text="x", retries=2)
    assert len(sent) == 1  # no retry loop against a dead server


async def test_http_errors_surface_unchanged():
    client, sent = make_client(400)
    with pytest.raises(openai.BadRequestError):
        await score_review(client, PARAMS, product=PRODUCT, review_text="x", retries=2)
    assert len(sent) == 1
