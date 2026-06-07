"""
backend/app/db.py

Async database engine, session factory, and dependency injection.

This is the single place that knows how to talk to PostgreSQL.
Every other file that needs a DB session uses the get_db() dependency —
never creates its own engine or session directly.

Architecture:
  engine             → one per process, manages the connection pool
  AsyncSessionLocal  → factory that creates individual sessions
  get_db()           → FastAPI dependency, yields one session per request
                       and guarantees cleanup even on exceptions
  get_db_context     → async context manager for scripts and background tasks
"""

from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

logger = structlog.get_logger(__name__)


# ── Engine ─────────────────────────────────────────────────

def _build_engine() -> AsyncEngine:
    kwargs = dict(
        echo=settings.is_development,
        future=True,
    )

    if settings.is_test:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 3600

    return create_async_engine(settings.database_url, **kwargs)


engine: AsyncEngine = _build_engine()


# ── Session factory ────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── FastAPI dependency ─────────────────────────────────────
# Usage in any route:
#
#   from app.db import get_db
#   from sqlalchemy.ext.asyncio import AsyncSession
#
#   @router.get("/something")
#   async def my_route(db: AsyncSession = Depends(get_db)):
#       result = await db.execute(...)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields one AsyncSession per request.
    Commits on clean exit, rolls back on exception.
    Always closes the session when the request is done.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.error("db_session_rolled_back", exc_info=True)
            raise
        finally:
            await session.close()


# ── Utility: get a session outside of FastAPI ──────────────
# Used in scripts, background tasks, and tests that
# don't go through FastAPI dependency injection.
#
# Usage:
#   async with get_db_context() as db:
#       result = await db.execute(...)

class get_db_context:
    """
    Async context manager for DB sessions outside FastAPI.
    """

    def __init__(self):
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self._session = AsyncSessionLocal()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session is None:
            return
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None