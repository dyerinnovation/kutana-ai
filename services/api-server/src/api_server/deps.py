"""Dependency injection functions for the API server."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        database_url: Async PostgreSQL connection string.
        redis_url: Redis connection string.
        cors_origins: Comma-separated list of allowed CORS origins.
        debug: Enable debug mode.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://convene:convene@localhost:5432/convene"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False
    jwt_secret: str = "change-me-in-production"
    agent_gateway_jwt_secret: str = "change-me-in-production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        The singleton Settings instance.
    """
    return Settings()


_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_session_factory(
    settings: Settings,
) -> async_sessionmaker[AsyncSession]:
    """Return a cached async session factory, creating it on first call.

    Args:
        settings: Application settings with database_url.

    Returns:
        An async sessionmaker bound to the configured engine.
    """
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _session_factory


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    """Yield an async database session and close it after use.

    Args:
        settings: Application settings injected by FastAPI.

    Yields:
        An AsyncSession connected to PostgreSQL.
    """
    factory = _build_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[Redis]:  # type: ignore[type-arg]  # redis-py stubs incomplete
    """Yield an async Redis client and close it after use.

    Args:
        settings: Application settings injected by FastAPI.

    Yields:
        A Redis async client instance.
    """
    client: Redis = Redis.from_url(  # type: ignore[assignment]  # redis-py stubs incomplete
        settings.redis_url,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()
