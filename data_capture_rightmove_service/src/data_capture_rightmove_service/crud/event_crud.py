from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.scrape_event import (
    ScrapeEvent,
    ScrapeEventTypeEnum,
)
from data_capture_rightmove_service.utils.logging_config import logger


async def log_scrape_event(
    db: AsyncSession,
    super_id: UUID,
    event_type: ScrapeEventTypeEnum,
    rightmove_property_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ScrapeEvent:
    """Logs a new scrape event to the database."""
    event = ScrapeEvent(
        super_id=super_id,
        event_type=event_type,
        rightmove_property_id=rightmove_property_id,
        payload=payload,
        **kwargs,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    logger.info(f"Logged event: {event_type.value} for super_id {super_id}")
    return event
