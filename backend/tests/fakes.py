import asyncio
from types import SimpleNamespace

import httpx
import openai

from app.ai import ProductDetails

DEFAULT_PRODUCT = ProductDetails(name="Galaxy S24", aspects=["battery life", "screen"])


class FakeLLM:
    """Duck-types AsyncOpenAI.chat.completions.parse for the whole app.

    Scoring rule: an aspect is "mentioned" when its name appears in the review;
    the score is 5 if the review says "great", otherwise 1. A review containing
    "BAD" gets an unparsable answer. `outage` simulates a dead server and `gate`
    blocks every call until it is set.
    """

    def __init__(self, product: ProductDetails | None = None, delay: float = 0.0):
        self.product = product or DEFAULT_PRODUCT
        self.delay = delay
        self.outage = False
        self.gate: asyncio.Event | None = None
        self.calls: list[dict] = []
        self.inflight = 0
        self.max_inflight = 0
        self.closed = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    async def _parse(self, **kwargs):
        self.calls.append(kwargs)
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.outage:
                raise openai.APIConnectionError(
                    request=httpx.Request("POST", "http://llm.invalid/v1")
                )
            response_format = kwargs["response_format"]
            system, user = (m["content"] for m in kwargs["messages"])
            if response_format is ProductDetails:
                parsed = self.product
            elif "BAD" in user:
                parsed = None
            else:
                aspects = [l[2:] for l in system.splitlines() if l.startswith("- ")]
                text = user.lower()
                score = 5 if "great" in text else 1
                parsed = response_format.model_validate(
                    {
                        "mentions": [
                            {"aspect": a, "score": score} for a in aspects if a in text
                        ]
                    }
                )
            message = SimpleNamespace(parsed=parsed, refusal=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        finally:
            self.inflight -= 1

    async def close(self) -> None:
        self.closed = True
