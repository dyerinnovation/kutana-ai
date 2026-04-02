"""Long-term memory layer using pgvector for semantic search.

Stores meeting summary embeddings in PostgreSQL with the pgvector
extension, enabling semantic similarity search across historical
meeting data.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Text, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

logger = logging.getLogger(__name__)

_EMBEDDING_DIMENSION = 1536


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class _Base(DeclarativeBase):
    """Declarative base for long-term memory ORM models."""


class MeetingSummaryEmbedding(_Base):
    """ORM model for meeting summary embeddings stored via pgvector.

    Attributes:
        id: Unique identifier for this embedding record.
        meeting_id: The meeting this summary belongs to.
        summary: Human-readable meeting summary text.
        embedding: Dense vector of floats for semantic search.
        created_at: When this embedding was stored.
    """

    __tablename__ = "meeting_summary_embeddings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    meeting_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(_EMBEDDING_DIMENSION), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class LongTermMemory:
    """pgvector-backed long-term memory for semantic meeting recall.

    Stores meeting summary embeddings and enables similarity search
    to find historically relevant meetings when the agent needs
    broader context.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize long-term memory with a SQLAlchemy session factory.

        Args:
            session_factory: An async session factory for database access.
        """
        self._session_factory = session_factory

    async def store_embedding(
        self,
        meeting_id: UUID,
        summary: str,
        embedding: list[float],
    ) -> None:
        """Store a meeting summary embedding for future semantic search.

        Args:
            meeting_id: UUID of the meeting the summary belongs to.
            summary: Human-readable summary text.
            embedding: Dense float vector (dimension must match
                the configured embedding dimension, default 1536).

        Raises:
            ValueError: If the embedding dimension does not match
                the configured dimension.
        """
        if len(embedding) != _EMBEDDING_DIMENSION:
            msg = f"Expected embedding dimension {_EMBEDDING_DIMENSION}, got {len(embedding)}"
            raise ValueError(msg)

        record = MeetingSummaryEmbedding(
            id=uuid4(),
            meeting_id=meeting_id,
            summary=summary,
            embedding=embedding,
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

        logger.info(
            "Stored embedding for meeting %s (%d chars summary).",
            meeting_id,
            len(summary),
        )

    async def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find meeting summaries semantically similar to a query.

        Uses pgvector's cosine distance operator to find the closest
        stored embeddings to the query vector.

        Args:
            query_embedding: Dense float vector to search against.
            limit: Maximum number of results to return.

        Returns:
            List of dictionaries with meeting_id, summary, and
            distance (lower is more similar), ordered by similarity.

        Raises:
            ValueError: If the query embedding dimension does not
                match the configured dimension.
        """
        if len(query_embedding) != _EMBEDDING_DIMENSION:
            msg = f"Expected embedding dimension {_EMBEDDING_DIMENSION}, got {len(query_embedding)}"
            raise ValueError(msg)

        async with self._session_factory() as session:
            # Use cosine distance for similarity ordering
            distance_expr = MeetingSummaryEmbedding.embedding.cosine_distance(query_embedding)
            stmt = (
                select(
                    MeetingSummaryEmbedding.meeting_id,
                    MeetingSummaryEmbedding.summary,
                    distance_expr.label("distance"),
                )
                .order_by(distance_expr)
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "meeting_id": str(row.meeting_id),
                    "summary": row.summary,
                    "distance": float(row.distance),
                }
                for row in rows
            ]
