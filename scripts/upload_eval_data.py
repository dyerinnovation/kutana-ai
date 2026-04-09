#!/usr/bin/env python3
"""Upload eval data (transcripts, scenarios, rubrics) to MinIO.

Usage:
    python scripts/upload_eval_data.py [--endpoint URL] [--bucket NAME]

Reads files from evals/data/ and uploads them to the kutana-eval-data
bucket in MinIO with the same directory structure.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EVALS_DATA_DIR = Path(__file__).resolve().parent.parent / "evals" / "data"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Upload eval data to MinIO")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:9000",
        help="MinIO endpoint URL (default: http://localhost:9000)",
    )
    parser.add_argument(
        "--bucket",
        default="kutana-eval-data",
        help="Target bucket name (default: kutana-eval-data)",
    )
    parser.add_argument(
        "--access-key",
        default="kutana",
        help="MinIO access key (default: kutana)",
    )
    parser.add_argument(
        "--secret-key",
        default="kutana-minio-secret",
        help="MinIO secret key (default: kutana-minio-secret)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be uploaded without uploading",
    )
    return parser.parse_args()


def ensure_bucket(client: boto3.client, bucket: str) -> None:
    """Create the bucket if it does not exist."""
    try:
        client.head_bucket(Bucket=bucket)
        logger.info("Bucket '%s' exists", bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=bucket)
        logger.info("Created bucket '%s'", bucket)


def collect_files(data_dir: Path) -> list[tuple[Path, str]]:
    """Collect all JSON files with their S3 keys.

    Args:
        data_dir: Root data directory (evals/data/).

    Returns:
        List of (local_path, s3_key) tuples.
    """
    files: list[tuple[Path, str]] = []
    for path in sorted(data_dir.rglob("*.json")):
        key = str(path.relative_to(data_dir))
        files.append((path, key))
    return files


def upload_files(
    client: boto3.client,
    bucket: str,
    files: list[tuple[Path, str]],
    dry_run: bool = False,
) -> int:
    """Upload files to MinIO.

    Args:
        client: S3 client.
        bucket: Target bucket.
        files: List of (local_path, s3_key) tuples.
        dry_run: If True, only print what would be uploaded.

    Returns:
        Number of files uploaded (or that would be uploaded).
    """
    count = 0
    for local_path, key in files:
        if dry_run:
            logger.info("[dry-run] Would upload: %s -> s3://%s/%s", local_path, bucket, key)
        else:
            content = local_path.read_bytes()
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType="application/json",
            )
            logger.info("Uploaded: %s -> s3://%s/%s", local_path.name, bucket, key)
        count += 1
    return count


def main() -> None:
    """Entry point."""
    args = parse_args()

    if not EVALS_DATA_DIR.exists():
        logger.error("Eval data directory not found: %s", EVALS_DATA_DIR)
        sys.exit(1)

    files = collect_files(EVALS_DATA_DIR)
    if not files:
        logger.warning("No JSON files found in %s", EVALS_DATA_DIR)
        sys.exit(0)

    logger.info("Found %d JSON files to upload", len(files))

    client = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )

    if not args.dry_run:
        ensure_bucket(client, args.bucket)

    count = upload_files(client, args.bucket, files, dry_run=args.dry_run)
    logger.info(
        "%s %d file(s) %s s3://%s/",
        "Would upload" if args.dry_run else "Uploaded",
        count,
        "to",
        args.bucket,
    )


if __name__ == "__main__":
    main()
