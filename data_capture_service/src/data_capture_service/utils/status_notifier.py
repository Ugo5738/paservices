"""
Uploads a JSON snapshot to S3 and returns a public URL (data_location).

Mirrors the pattern established in floorplan_service for consistency
across the orchestrator workflow.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional
from uuid import UUID

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

from data_capture_service.config import settings

logger = logging.getLogger(__name__)


def _serialize_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class StatusNotifier:
    """Uploads JSON snapshots to S3 and returns public URLs."""

    def __init__(self) -> None:
        if not boto3:
            raise RuntimeError("boto3 is required for S3 uploads but is not installed.")
        if not settings.STATUS_S3_BUCKET_NAME:
            raise RuntimeError(
                "STATUS_S3_BUCKET_NAME must be configured to enable status snapshots."
            )

        self.bucket = settings.STATUS_S3_BUCKET_NAME
        self.prefix = settings.STATUS_S3_PREFIX.strip("/")
        self.region = settings.STATUS_S3_REGION
        self.public_base_url = (
            settings.STATUS_S3_PUBLIC_BASE_URL.rstrip("/")
            if settings.STATUS_S3_PUBLIC_BASE_URL
            else None
        )
        self.endpoint_url = settings.STATUS_S3_ENDPOINT_URL

        boto3_kwargs: Dict[str, str] = {}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            boto3_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            boto3_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        if settings.AWS_SESSION_TOKEN:
            boto3_kwargs["aws_session_token"] = settings.AWS_SESSION_TOKEN
        if self.region:
            boto3_kwargs["region_name"] = self.region
        if self.endpoint_url:
            boto3_kwargs["endpoint_url"] = self.endpoint_url

        self._s3_client = boto3.client("s3", **boto3_kwargs)  # type: ignore[arg-type]

    def _build_s3_key(self, context: str, super_id: UUID | str) -> str:
        context_segment = context.strip("/") or "generic"
        return f"{self.prefix}/{context_segment}/{super_id}/status.json"

    def _build_public_url(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        if self.endpoint_url:
            base = self.endpoint_url.rstrip("/")
            return f"{base}/{self.bucket}/{key}"
        if self.region and self.region != "us-east-1":
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"

    async def upload_snapshot(
        self,
        *,
        super_id: UUID | str,
        context: str,
        snapshot: Dict[str, Any],
    ) -> str:
        """Upload a JSON snapshot to S3 and return its public URL."""
        key = self._build_s3_key(context, super_id)
        payload = json.dumps(snapshot, default=_serialize_default).encode("utf-8")

        def _put_object() -> None:
            self._s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                CacheControl="no-cache",
            )

        await asyncio.to_thread(_put_object)
        return self._build_public_url(key)


@lru_cache(maxsize=1)
def get_status_notifier() -> Optional[StatusNotifier]:
    """Return a singleton StatusNotifier, or None if S3 is not configured."""
    if not settings.status_notifications_enabled():
        return None
    try:
        return StatusNotifier()
    except Exception as exc:  # pragma: no cover
        logger.error(f"StatusNotifier unavailable: {exc}", exc_info=True)
        return None
