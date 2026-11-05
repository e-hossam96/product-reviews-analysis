from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.ai.schemas import MAX_ASPECT_LENGTH, MAX_SCORE, MIN_SCORE
from app.models import JobStatus

# Named constraints keep Alembic batch migrations on SQLite predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ReviewStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


def utcnow() -> datetime:
    # SQLite drops tzinfo, so everything is stored as UTC and compared as UTC.
    return datetime.now(timezone.utc)


def new_session_id() -> str:
    # The id doubles as the bearer token, so it must be unguessable.
    return secrets.token_urlsafe(32)


def new_job_id() -> str:
    return uuid.uuid4().hex


class AnalysisSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_session_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    # ProductDetails as JSON; SQL NULL until extracted
    product: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    product_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("session_id", "row_index", name="uq_reviews_session_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    row_index: Mapped[int] = mapped_column(Integer)  # position in the uploaded CSV
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ReviewStatus.PENDING.value)
    error: Mapped[str | None] = mapped_column(Text)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("review_id", "aspect", name="uq_scores_review_aspect"),
        CheckConstraint(f"score BETWEEN {MIN_SCORE} AND {MAX_SCORE}", name="score_range"),
        Index("ix_scores_session_aspect", "session_id", "aspect"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"))
    # denormalized so aggregation doesn't need a join through reviews
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    aspect: Mapped[str] = mapped_column(String(MAX_ASPECT_LENGTH))
    score: Mapped[int] = mapped_column(Integer)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_job_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.PENDING.value)
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
