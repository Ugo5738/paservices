"""Helpers for persisting workflow status snapshots."""

from typing import Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from data_capture_rightmove_service.crud.workflow_status_crud import upsert_status
from data_capture_rightmove_service.db import AsyncSessionLocal
from data_capture_rightmove_service.utils.logging_config import logger


async def record_workflow_status(
    *,
    super_id: UUID | str,
    context: str,
    status: str,
    property_id: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    data_location: Optional[str] = None,
    last_error: Optional[str] = None,
) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await upsert_status(
                session,
                super_id=UUID(str(super_id)),
                context=context,
                property_id=property_id,
                status=status,
                stage=stage,
                progress=progress,
                data_location=data_location,
                last_error=last_error,
            )
            await session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive logging
            await session.rollback()
            logger.error(
                "Failed to persist workflow status",
                exc_info=True,
                extra={
                    "super_id": str(super_id),
                    "context": context,
                    "status": status,
                },
            )
            raise exc

    # Chunk 4.5: record each status transition as an activity event on
    # the SuperID Metadata store. The workflow_status row carries latest
    # state (upserted above); the activity record is the immutable per-
    # transition audit trail. Non-blocking.
    from data_capture_rightmove_service.clients.super_id_service_client import (
        super_id_service_client,
    )

    await super_id_service_client.record_activity(
        super_id=UUID(str(super_id)),
        used_by="data_capture_rightmove_service",
        source=f"rightmove/workflow_status/{context}/{status}",
        metadata={
            "context": context,
            "status": status,
            "stage": stage,
            "progress": progress,
            "property_id": property_id,
            "has_error": last_error is not None,
        },
    )
