"""MinIO / S3-compatible client for loading eval data."""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "kutana-eval-data"
DEFAULT_ENDPOINT = "http://localhost:9000"


class EvalMinioClient:
    """Thin wrapper around boto3 S3 client for eval data access.

    Args:
        endpoint_url: MinIO / S3 endpoint.
        access_key: Access key ID.
        secret_key: Secret access key.
        bucket: Bucket name.
    """

    def __init__(
        self,
        endpoint_url: str = DEFAULT_ENDPOINT,
        access_key: str = "kutana",
        secret_key: str = "kutana-minio-secret",
        bucket: str = DEFAULT_BUCKET,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def load_json(self, key: str) -> Any:
        """Download and parse a JSON object from the eval bucket.

        Args:
            key: S3 object key (e.g. ``transcripts/standup-10min.json``).

        Returns:
            Parsed JSON content.
        """
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))

    def list_keys(self, prefix: str = "") -> list[str]:
        """List object keys under a prefix.

        Args:
            prefix: S3 key prefix to filter by.

        Returns:
            List of matching object keys.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def upload_json(self, key: str, data: Any) -> None:
        """Upload a JSON-serialisable object to the eval bucket.

        Args:
            key: S3 object key.
            data: Object to serialise as JSON.
        """
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )

    def ensure_bucket(self) -> None:
        """Create the eval bucket if it does not exist."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except self._client.exceptions.ClientError:
            self._client.create_bucket(Bucket=self._bucket)
            logger.info("Created bucket %s", self._bucket)
