"""Cloudflare R2 (S3-compatible) upload helper.

Centralizes the boto3 client setup so it isn't duplicated across the burner
and reframer service classes. Uploads are retried with exponential backoff
to handle transient S3/R2 errors.
"""

from __future__ import annotations

import logging
import os

from errors import UploadError
from utils import retry

logger = logging.getLogger("makemyclip.r2")

REQUIRED_ENV_VARS = (
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_PUBLIC_URL",
)


def assert_r2_env() -> None:
    """Raise immediately if any required R2 env var is missing."""
    missing = [k for k in REQUIRED_ENV_VARS if not os.environ.get(k)]
    if missing:
        raise UploadError(f"Missing required R2 env vars: {missing}")


def get_r2_client():
    """Return a configured boto3 S3 client targeting R2."""
    import boto3

    assert_r2_env()
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )


@retry(max_attempts=3, backoff_base=2.0, retryable=(Exception,))
def upload_to_r2(local_path: str, key: str, *, bucket: str | None = None) -> str:
    """Upload ``local_path`` to ``key`` and return the public URL.

    Retries up to 3 times with exponential backoff on transient failures.
    """
    s3 = get_r2_client()
    bucket_name = bucket or os.environ.get("R2_BUCKET_NAME", "makemyclip")

    file_size = os.path.getsize(local_path)
    logger.info(
        "Uploading %s (%s bytes) to R2 bucket=%s key=%s",
        local_path,
        f"{file_size:,}",
        bucket_name,
        key,
    )

    s3.upload_file(local_path, bucket_name, key)

    public_url = f"{os.environ['R2_PUBLIC_URL']}/{key}"
    logger.info("Upload complete: %s", public_url)
    return public_url
