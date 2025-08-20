import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.floorplan_models import FloorplanEvent, FloorplanEventTypeEnum
from ..utils.logging_config import logger


async def log_floorplan_event(
    db: AsyncSession,
    super_id: uuid.UUID,
    event_type: FloorplanEventTypeEnum,
    floorplan_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
):
    """Logs a floorplan analysis event to the database."""
    try:
        event = FloorplanEvent(
            super_id=super_id,
            event_type=event_type,
            floorplan_id=floorplan_id,
            details=details,
            error_message=error_message,
        )
        db.add(event)
        await db.flush()
        logger.info(f"Logged event '{event_type.name}' for super_id '{super_id}'")
    except Exception as e:
        logger.error(
            f"Failed to log event '{event_type.name}' for super_id '{super_id}': {e}",
            exc_info=True,
        )
