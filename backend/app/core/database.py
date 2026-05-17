"""Async database persistence for conversations and execution traces."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for application-managed columns."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM tables."""


class ConversationRecord(Base):
    """Persisted chat conversation."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    messages: Mapped[list["MessageRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class MessageRecord(Base):
    """Persisted user or assistant message."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="messages")


class LlmInvocationRecord(Base):
    """Persisted record of one LLM request/response."""

    __tablename__ = "llm_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ToolRunRecord(Base):
    """Persisted result of one executed Planner task/API call."""

    __tablename__ = "tool_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    assistant_message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    planner_invocation_id: Mapped[str] = mapped_column(
        ForeignKey("llm_invocations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(String(80), nullable=False)
    tool: Mapped[str] = mapped_column(String(120), nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


def normalize_database_url(database_url: str) -> str:
    """Normalize database URLs for SQLAlchemy async engines."""
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    if database_url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(database_url)

        query_params = dict(parse_qsl(parts.query, keep_blank_values=True))

        # Neon/Vercel/Postgres URLs sometimes include params that asyncpg
        # does not accept as connect() keyword arguments.
        query_params.pop("channel_binding", None)

        # asyncpg expects ssl=require instead of sslmode=require
        if query_params.get("sslmode") == "require":
            query_params.pop("sslmode", None)
            query_params["ssl"] = "require"

        cleaned_query = urlencode(query_params)

        database_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                cleaned_query,
                parts.fragment,
            )
        )

    return database_url

def make_engine(database_url: str) -> AsyncEngine:
    """Build the async SQLAlchemy engine for the configured database URL."""
    database_url = normalize_database_url(database_url)
    url = make_url(database_url)

    if url.drivername.startswith("sqlite"):
        _prepare_sqlite_path(database_url)
        return create_async_engine(database_url, future=True)

    return create_async_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the app-wide async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create tables if they do not already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _prepare_sqlite_path(database_url: str) -> None:
    """Ensure local SQLite database files live in writable directories."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or url.database in (None, "", ":memory:"):
        return

    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        mode = db_path.stat().st_mode
        user_write_bit = 0o200
        if not mode & user_write_bit:
            db_path.chmod(mode | user_write_bit)
