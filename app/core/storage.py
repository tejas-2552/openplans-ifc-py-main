"""Cloud storage abstraction for uploading generated IFC files.

Supports three backends selected via the ``STORAGE_BACKEND`` env var:
    - ``gcs``   → Google Cloud Storage (signed URL)
    - ``s3``    → AWS S3 (pre-signed URL)
    - ``local`` → Fallback for development (returns local path)
"""

from __future__ import annotations

import os
import datetime
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Interface every storage backend must implement."""

    @abstractmethod
    def upload(self, local_path: str) -> str:
        """Upload *local_path* and return a download URL / path."""
        ...


# ── Google Cloud Storage ──────────────────────────────────────────

class GCSBackend(StorageBackend):
    """Upload to a GCS bucket and return a signed download URL."""

    def __init__(self) -> None:
        from google.cloud import storage as gcs  # lazy import

        self._bucket_name = os.environ["GCS_BUCKET"]
        self._client = gcs.Client()
        self._bucket = self._client.bucket(self._bucket_name)

    def upload(self, local_path: str) -> str:
        blob_name = Path(local_path).name
        blob = self._bucket.blob(blob_name)
        blob.upload_from_filename(local_path)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET",
        )
        return url


# ── AWS S3 ────────────────────────────────────────────────────────

class S3Backend(StorageBackend):
    """Upload to S3 and return a pre-signed download URL."""

    def __init__(self) -> None:
        import boto3  # lazy import

        self._bucket_name = os.environ["S3_BUCKET"]
        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._s3 = boto3.client("s3", region_name=self._region)

    def upload(self, local_path: str) -> str:
        key = Path(local_path).name
        self._s3.upload_file(local_path, self._bucket_name, key)
        url = self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": key},
            ExpiresIn=3600,
        )
        return url


# ── Local fallback (dev) ─────────────────────────────────────────

class LocalBackend(StorageBackend):
    """No upload — just return the local path.  For development only."""

    def upload(self, local_path: str) -> str:
        return local_path


# ── Factory ───────────────────────────────────────────────────────

def get_storage_backend() -> StorageBackend:
    """Select a backend based on the ``STORAGE_BACKEND`` env var.

    Defaults to ``local`` when the variable is unset.
    """
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend == "gcs":
        return GCSBackend()
    if backend == "s3":
        return S3Backend()
    return LocalBackend()
