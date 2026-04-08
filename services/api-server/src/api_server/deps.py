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

from api_server.event_publisher import EventPublisher

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

    database_url: str = "postgresql+asyncpg://kutana:kutana@localhost:5432/kutana"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False
    jwt_secret: str = "change-me-in-production"
    agent_gateway_jwt_secret: str = "change-me-in-production"

    # Object storage (S3-compatible — MinIO in dev, cloud in prod)
    storage_provider: str = "s3"
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "kutana-uploads"
    storage_region: str = "us-east-1"
    storage_use_ssl: bool = False
    storage_access_key: str = "kutana"
    storage_secret_key: str = "kutana-minio-secret"

    # Stripe billing
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_basic_monthly: str = ""
    stripe_price_basic_yearly: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_yearly: str = ""
    stripe_price_business_monthly: str = ""
    stripe_price_business_yearly: str = ""
    stripe_trial_days: int = 14
    billing_success_url: str = "http://localhost:5173/settings/billing?status=success"
    billing_cancel_url: str = "http://localhost:5173/pricing?status=cancel"
    billing_portal_return_url: str = "http://localhost:5173/settings/billing"

    # SMTP (SendGrid / SES)
    smtp_host: str = ""
    smtp_from: str = "noreply@kutana.ai"
    smtp_api_key: str = ""

    # Slack OAuth
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_redirect_uri: str = ""
    frontend_url: str = "http://localhost:5173"

    # Observability
    sentry_dsn: str = ""
    slack_webhook_url: str = ""
    log_format: str = "json"  # "json" or "text"


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


async def get_event_publisher(
    redis_client: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> EventPublisher:
    """Return an EventPublisher wired to the active Redis client.

    Args:
        redis_client: Redis client provided by :func:`get_redis`.

    Returns:
        An :class:`~api_server.event_publisher.EventPublisher` instance.
    """
    return EventPublisher(redis_client)
