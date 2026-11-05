from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings
from app.utils import logger


def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # required for ON DELETE CASCADE
    cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the job's writes
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class DatabaseClient:
    """Long-lived: create once (lifespan), close once, share everywhere."""

    def __init__(self, config: DatabaseSettings):
        self.engine: AsyncEngine = create_async_engine(
            config.database_url,
            echo=False,
            pool_pre_ping=True,
            json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
        )
        event.listen(self.engine.sync_engine, "connect", _set_sqlite_pragmas)
        self._sessionmaker = async_sessionmaker(bind=self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """One transaction: commits on success, rolls back on any exception."""
        async with self._sessionmaker.begin() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
        logger.debug("Database engine disposed")

    async def __aenter__(self) -> DatabaseClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
