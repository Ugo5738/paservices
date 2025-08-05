import json
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.scrape_event import (
    ScrapeEvent,
    ScrapeEventTypeEnum,
)
from data_capture_rightmove_service.utils.logging_config import logger


def _make_payload_json_serializable(payload: Any) -> Any:
    """
    Recursively walks through a payload and converts non-serializable types.
    Specifically handles UUID objects by converting them to strings.
    """
    if isinstance(payload, dict):
        return {k: _make_payload_json_serializable(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_make_payload_json_serializable(i) for i in payload]
    if isinstance(payload, UUID):
        return str(payload)
    return payload


async def log_scrape_event(
    db: AsyncSession,
    super_id: UUID,
    event_type: ScrapeEventTypeEnum,
    rightmove_property_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ScrapeEvent:
    """Logs a new scrape event to the database."""

    # Sanitize the payload before creating the model instance
    sanitized_payload = _make_payload_json_serializable(payload)

    event = ScrapeEvent(
        super_id=super_id,
        event_type=event_type,
        rightmove_property_id=rightmove_property_id,
        payload=sanitized_payload,
        **kwargs,
    )
    db.add(event)
    # await db.commit()
    await db.flush()
    await db.refresh(event)
    logger.info(f"Logged event: {event_type.value} for super_id {super_id}")
    return event
