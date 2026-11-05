from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import openai
from fastapi import Depends, HTTPException, Path, Request, status

from app.ai import LLMOutputError
from app.database.client import DatabaseClient
from app.database.models import AnalysisSession
from app.utils import logger

# The session id is the user's access token: random, URL-safe, and validated on entry.
SessionId = Annotated[str, Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


def get_db(request: Request) -> DatabaseClient:
    return request.app.state.db


DbDep = Annotated[DatabaseClient, Depends(get_db)]


async def get_session(session_id: SessionId, db: DbDep) -> AnalysisSession:
    async with db.session() as s:
        session = await s.get(AnalysisSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")
    return session


SessionRequired = Depends(get_session)


@contextmanager
def llm_errors() -> Iterator[None]:
    """Turn LLM failures into HTTP errors the frontend can show."""
    try:
        yield
    except LLMOutputError as e:
        logger.warning("LLM returned no valid output: %s", e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The model did not return a valid answer. Please try again.",
        ) from e
    except openai.APIConnectionError as e:
        logger.error("LLM server unreachable: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The language model server is unreachable.",
        ) from e
    except openai.OpenAIError as e:
        logger.error("LLM request failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The language model request failed.") from e
