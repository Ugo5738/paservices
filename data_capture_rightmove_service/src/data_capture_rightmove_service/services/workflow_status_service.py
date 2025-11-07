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
