"""Langfuse tracing helpers. Everything here is a no-op when tracing is off."""

import hashlib
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from app.core.config import get_settings


def tracing_enabled() -> bool:
    return get_settings().langfuse.enabled


def call_kwargs(step: str) -> dict[str, Any]:
    """Per-call options for the Langfuse-wrapped OpenAI client.

    Empty when tracing is off: the plain OpenAI client rejects unknown arguments.
    Only `name` goes here. The Langfuse wrapper forwards `session_id` and `tags` to
    the model server, which would fail, so those use `trace_session` instead.
    """
    return {"name": step} if tracing_enabled() else {}


def trace_session(session_id: str, step: str) -> AbstractContextManager[Any]:
    """Group every LLM call made inside the block under one Langfuse session.

    The Langfuse session id is a hash: the real session id is an access token and
    must not be copied into a third-party system.
    """
    if not tracing_enabled():
        return nullcontext()
    from langfuse import propagate_attributes

    digest = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return propagate_attributes(session_id=digest, tags=[step])
