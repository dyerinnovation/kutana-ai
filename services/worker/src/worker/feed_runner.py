"""FeedRunner — consumes feed-run records and executes feed agents.

Reads from the ``convene:feed-runs`` stream and launches a FeedAgent
for each pending run. Handles retries with exponential backoff (max 3
attempts per run).
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from sqlalchemy import select

from api_server.encryption import decrypt_value
from convene_core.database.models import FeedORM, FeedRunORM, FeedSecretORM
from convene_core.feeds.adapters import build_adapter
from worker.feed_agent import run_feed

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

FEED_RUNS_STREAM = "convene:feed-runs"
DEFAULT_GROUP_NAME = "feed-runner"
DEFAULT_BLOCK_MS = 5_000
DEFAULT_BATCH_SIZE = 5
_MAX_BACKOFF_SECONDS = 30
_MAX_RETRIES = 3

# Concurrency limiter — avoid hammering external APIs during post-meeting burst
_MAX_CONCURRENT_AGENTS = 3


class FeedRunner:
    """Picks up FeedRun records and launches feed agents.

    Attributes:
        _redis_url: Redis connection URL.
        _session_factory: SQLAlchemy async session factory.
        _convene_mcp_url: URL of the Convene MCP server.
        _convene_mcp_token: Bearer token for the Convene MCP server.
    """

    def __init__(
        self,
        redis_url: str,
        session_factory: async_sessionmaker[AsyncSession],
        convene_mcp_url: str = "http://localhost:3001/mcp",
        convene_mcp_token: str = "",
        group_name: str = DEFAULT_GROUP_NAME,
        consumer_name: str | None = None,
        block_ms: int = DEFAULT_BLOCK_MS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """Initialise the runner.

        Args:
            redis_url: Redis connection URL.
            session_factory: SQLAlchemy async session factory.
            convene_mcp_url: URL of the Convene MCP server.
            convene_mcp_token: Bearer token for the Convene MCP server.
            group_name: Consumer group name.
            consumer_name: Unique name for this consumer.
            block_ms: Milliseconds XREADGROUP blocks per call.
            batch_size: Max entries per XREADGROUP call.
        """
        self._redis_url = redis_url
        self._session_factory = session_factory
        self._convene_mcp_url = convene_mcp_url
        self._convene_mcp_token = convene_mcp_token
        self._group_name = group_name
        self._consumer_name = consumer_name or f"feed-runner-{socket.gethostname()}"
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._redis: redis.Redis[str] | None = None
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AGENTS)

    async def start(self) -> None:
        """Connect to Redis, ensure consumer group, then run the consume loop."""
        self._stop_event.clear()
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        logger.info(
            "FeedRunner starting (stream=%s, group=%s, consumer=%s)",
            FEED_RUNS_STREAM,
            self._group_name,
            self._consumer_name,
        )
        try:
            await self._ensure_group()
            await self._consume_loop()
        finally:
            await self._close_redis()

    async def stop(self) -> None:
        """Signal the consume loop to exit."""
        logger.info("FeedRunner stop requested")
        self._stop_event.set()

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not exist."""
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(
                FEED_RUNS_STREAM,
                self._group_name,
                id="$",
                mkstream=True,
            )
            logger.info("Created consumer group '%s' on '%s'", self._group_name, FEED_RUNS_STREAM)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("Consumer group '%s' already exists", self._group_name)
            else:
                raise

    async def _consume_loop(self) -> None:
        """Main XREADGROUP loop."""
        assert self._redis is not None
        backoff = 1.0

        while not self._stop_event.is_set():
            try:
                response = await self._redis.xreadgroup(
                    groupname=self._group_name,
                    consumername=self._consumer_name,
                    streams={FEED_RUNS_STREAM: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
                backoff = 1.0

                if not response:
                    continue

                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        await self._handle_entry(entry_id, fields)

            except asyncio.CancelledError:
                logger.info("FeedRunner cancelled")
                raise
            except RedisConnectionError as exc:
                if self._stop_event.is_set():
                    break
                logger.warning("Redis connection error: %s — retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                await self._close_redis()
                self._redis = redis.from_url(self._redis_url, decode_responses=True)
                await self._ensure_group()
            except Exception:
                logger.exception("Unexpected error in FeedRunner consume loop")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

        logger.info("FeedRunner loop exited")

    async def _handle_entry(self, entry_id: str, fields: dict[str, str]) -> None:
        """Process a single feed-run entry.

        Args:
            entry_id: Redis stream entry ID.
            fields: Entry fields.
        """
        assert self._redis is not None

        raw_payload = fields.get("payload", "")
        try:
            data = json.loads(raw_payload)
            feed_id = UUID(data["feed_id"])
            feed_run_id = UUID(data["feed_run_id"])
            meeting_id = UUID(data["meeting_id"])
            direction = data["direction"]
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.exception("Failed to parse feed-run payload (entry=%s)", entry_id)
            await self._ack(entry_id)
            return

        async with self._semaphore:
            await self._execute_run(feed_id, feed_run_id, meeting_id, direction)

        await self._ack(entry_id)

    async def _execute_run(
        self,
        feed_id: UUID,
        feed_run_id: UUID,
        meeting_id: UUID,
        direction: str,
    ) -> None:
        """Execute a single feed run with retry logic.

        Args:
            feed_id: Feed UUID.
            feed_run_id: FeedRun UUID.
            meeting_id: Meeting UUID.
            direction: Run direction.
        """
        async with self._session_factory() as session:
            # Load feed and run
            feed_result = await session.execute(select(FeedORM).where(FeedORM.id == feed_id))
            feed = feed_result.scalar_one_or_none()
            if feed is None:
                logger.warning("Feed %s not found — skipping run %s", feed_id, feed_run_id)
                return

            run_result = await session.execute(
                select(FeedRunORM).where(FeedRunORM.id == feed_run_id)
            )
            run = run_result.scalar_one_or_none()
            if run is None:
                logger.warning("FeedRun %s not found — skipping", feed_run_id)
                return

            # Decrypt token if MCP feed
            decrypted_token: str | None = None
            if feed.delivery_type == "mcp":
                secret_result = await session.execute(
                    select(FeedSecretORM).where(FeedSecretORM.feed_id == feed_id)
                )
                secret = secret_result.scalar_one_or_none()
                if secret is not None:
                    try:
                        decrypted_token = decrypt_value(secret.encrypted_token)
                    except ValueError:
                        logger.exception("Failed to decrypt token for feed %s", feed_id)
                        run.status = "failed"
                        run.error = "Token decryption failed"
                        run.finished_at = datetime.now(tz=UTC)
                        await session.commit()
                        return

            # Build adapter
            try:
                adapter = build_adapter(feed, decrypted_token)
            except ValueError as e:
                logger.error("Failed to build adapter for feed %s: %s", feed_id, e)
                run.status = "failed"
                run.error = str(e)
                run.finished_at = datetime.now(tz=UTC)
                await session.commit()
                return

            # Update run to running
            run.status = "running"
            await session.commit()

            # Execute with retry
            last_error: str | None = None
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    await run_feed(
                        feed=feed,
                        meeting_id=meeting_id,
                        direction=direction,
                        adapter=adapter,
                        convene_mcp_url=self._convene_mcp_url,
                        convene_mcp_token=self._convene_mcp_token,
                    )
                    # Success
                    run.status = "delivered"
                    run.finished_at = datetime.now(tz=UTC)
                    feed.last_triggered_at = datetime.now(tz=UTC)
                    feed.last_error = None
                    await session.commit()
                    logger.info(
                        "Feed run delivered: run=%s feed=%s meeting=%s",
                        feed_run_id,
                        feed.name,
                        meeting_id,
                    )
                    return
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        "Feed run attempt %d/%d failed: run=%s error=%s",
                        attempt,
                        _MAX_RETRIES,
                        feed_run_id,
                        last_error,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(2**attempt)

            # All retries exhausted
            run.status = "failed"
            run.error = last_error
            run.finished_at = datetime.now(tz=UTC)
            feed.last_error = last_error
            await session.commit()
            logger.error(
                "Feed run failed after %d attempts: run=%s feed=%s",
                _MAX_RETRIES,
                feed_run_id,
                feed.name,
            )

    async def _ack(self, entry_id: str) -> None:
        """Acknowledge a stream entry.

        Args:
            entry_id: The Redis stream entry ID.
        """
        assert self._redis is not None
        await self._redis.xack(FEED_RUNS_STREAM, self._group_name, entry_id)

    async def _close_redis(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
