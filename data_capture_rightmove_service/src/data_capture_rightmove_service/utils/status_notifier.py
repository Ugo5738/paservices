"""
Utility for broadcasting workflow status updates to S3 and optional webhooks.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

try:
    import boto3
except ImportError:  # pragma: no cover - runtime guard
    boto3 = None  # type: ignore

from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.services.workflow_status_service import (
    record_workflow_status,
)
from data_capture_rightmove_service.utils.logging_config import logger


def _serialize_default(obj: Any) -> str:
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    return str(obj)


class StatusNotifier:
    """Handles S3 snapshot uploads and webhook notifications."""

    def __init__(self):
        if not boto3:
            raise RuntimeError("boto3 is required for S3 notifications but is not installed.")

        if not settings.STATUS_S3_BUCKET_NAME:
            raise RuntimeError("STATUS_S3_BUCKET_NAME must be configured to enable status notifications.")

        self.bucket = settings.STATUS_S3_BUCKET_NAME
        self.prefix = settings.STATUS_S3_PREFIX.strip("/")
        self.region = settings.STATUS_S3_REGION
        self.public_base_url = (
            settings.STATUS_S3_PUBLIC_BASE_URL.rstrip("/")
            if settings.STATUS_S3_PUBLIC_BASE_URL
            else None
        )
        self.webhook_url = settings.STATUS_WEBHOOK_URL
        self.webhook_headers = settings.STATUS_WEBHOOK_HEADERS or {}
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

    async def _upload_snapshot(self, key: str, snapshot: Dict[str, Any]) -> str:
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

    async def _post_webhook(
        self,
        body: Dict[str, Any],
        *,
        webhook_url: Optional[str] = None,
        webhook_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        url = webhook_url or self.webhook_url
        if not url:
            return
        if not isinstance(url, str):
            url = str(url)
        headers = webhook_headers or self.webhook_headers
        safe_body = json.loads(json.dumps(body, default=_serialize_default))

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=safe_body,
                    headers=headers,
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover - logging only
            logger.error(
                "Failed to send status webhook to %s: %s",
                url,
                exc,
                extra={"webhook_url": url, "error": str(exc)},
            )

    async def notify(
        self,
        *,
        super_id: UUID | str,
        status: str,
        context: str,
        data: Dict[str, Any],
        summary: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
        webhook_headers: Optional[Dict[str, str]] = None,
        property_id: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        last_error: Optional[str] = None,
    ) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "super_id": str(super_id),
            "context": context,
            "status": status,
            "timestamp": timestamp,
            "summary": summary or {},
            "metadata": metadata or {},
            "data": data,
        }

        key = self._build_s3_key(context, super_id)
        snapshot_url = await self._upload_snapshot(key, snapshot)

        await self._post_webhook(
            {
                "super_id": str(super_id),
                "status": status,
                "context": context,
                "data_location": snapshot_url,
                "timestamp": timestamp,
                "summary": summary or {},
                "metadata": metadata or {},
            },
            webhook_url=webhook_url,
            webhook_headers=webhook_headers,
        )

        try:
            await record_workflow_status(
                super_id=super_id,
                context=context,
                status=status,
                property_id=property_id,
                stage=stage,
                progress=progress,
                data_location=snapshot_url,
                last_error=last_error,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to persist workflow status",
                exc_info=True,
                extra={"super_id": str(super_id), "context": context, "error": str(exc)},
            )

        return snapshot_url


@lru_cache(maxsize=1)
def get_status_notifier() -> Optional[StatusNotifier]:
    if not settings.status_notifications_enabled():
        return None
    try:
        return StatusNotifier()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Status notifier unavailable: {exc}", exc_info=True)
        return None
