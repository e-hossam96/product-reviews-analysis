import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.database.client import DatabaseClient
from app.database.models import AnalysisSession, Job, utcnow
from app.jobs import ACTIVE_STATUSES
from app.utils import logger


async def delete_expired_sessions(
    db: DatabaseClient, ttl_hours: int, *, now: datetime | None = None
) -> int:
    """Delete sessions older than the TTL, except those with a job in progress.

    Reviews, scores and jobs go with them through ON DELETE CASCADE.
    """
    cutoff = (now or utcnow()) - timedelta(hours=ttl_hours)
    active = select(Job.session_id).where(Job.status.in_(ACTIVE_STATUSES))
    async with db.session() as s:
        result = await s.execute(
            delete(AnalysisSession).where(
                AnalysisSession.created_at < cutoff,
                AnalysisSession.id.not_in(active),
            )
        )
        return result.rowcount or 0


async def cleanup_loop(db: DatabaseClient, *, ttl_hours: int, interval_minutes: int) -> None:
    while True:
        try:
            deleted = await delete_expired_sessions(db, ttl_hours)
            if deleted:
                logger.info("Deleted %d expired session(s)", deleted)
        except Exception:
            logger.exception("Session cleanup failed")
        await asyncio.sleep(interval_minutes * 60)
