"""Async database session management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def create_engine(url: str, **kwargs: object) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        url: Database connection URL (e.g.,
            "postgresql+asyncpg://user:pass@host/db").
        **kwargs: Additional keyword arguments passed to
            create_async_engine.

    Returns:
        An AsyncEngine instance.
    """
    return create_async_engine(url, echo=False, **kwargs)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        An async_sessionmaker configured for the engine.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield an async database session for FastAPI dependency injection.

    Usage with FastAPI::

        engine = create_engine(DATABASE_URL)
        SessionFactory = create_session_factory(engine)

        async def get_db() -> AsyncIterator[AsyncSession]:
            async for session in get_session(SessionFactory):
                yield session

        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    Args:
        session_factory: The async session factory to create sessions from.

    Yields:
        An AsyncSession instance that is automatically closed.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
