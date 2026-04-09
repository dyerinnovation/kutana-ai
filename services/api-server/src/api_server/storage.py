"""S3-compatible object storage client.

Works with MinIO (dev), AWS S3, Cloudflare R2, or GCS (S3-compat mode).
Switch providers by changing STORAGE_ENDPOINT and credentials — no code changes.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

import boto3
from botocore.config import Config as BotoConfig

logger = logging.getLogger(__name__)


class ObjectStorage:
    """Async wrapper around a boto3 S3 client."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_ssl: bool = False,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=use_ssl,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    async def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""

        def _ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except self._client.exceptions.ClientError:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("Created bucket %s", self._bucket)

        await asyncio.to_thread(_ensure)

    async def upload(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload bytes to the bucket.

        Args:
            key: Object key (path within bucket).
            data: File content.
            content_type: MIME type.

        Returns:
            The object key.
        """
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Generate a presigned GET URL.

        Args:
            key: Object key.
            expires: URL lifetime in seconds.

        Returns:
            A presigned URL string.
        """
        url: str = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
        return url

    async def delete(self, key: str) -> None:
        """Delete an object from the bucket.

        Args:
            key: Object key.
        """
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=key,
        )


_storage: ObjectStorage | None = None


@lru_cache(maxsize=1)
def _build_storage() -> ObjectStorage:
    """Build and cache a storage client from settings."""
    from api_server.deps import get_settings

    settings = get_settings()
    return ObjectStorage(
        endpoint=settings.storage_endpoint,
        bucket=settings.storage_bucket,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        region=settings.storage_region,
        use_ssl=settings.storage_use_ssl,
    )


def get_storage() -> ObjectStorage:
    """FastAPI dependency that returns the cached ObjectStorage client.

    Returns:
        The singleton ObjectStorage instance.
    """
    return _build_storage()
