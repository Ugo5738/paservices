"""
CRUD operations for SourceRawRecord and SourceParsedRecord models.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.source_parsed_record import SourceParsedRecord
from data_capture_service.models.source_raw_record import SourceRawRecord


async def store_raw_record(
    db: AsyncSession,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    adapter_name: str,
    payload_json: Optional[Dict[str, Any]] = None,
    source_domain: Optional[str] = None,
    http_status_code: Optional[int] = None,
    http_meta_json: Optional[Dict[str, Any]] = None,
    content_hash: Optional[str] = None,
) -> SourceRawRecord:
    """Store a raw data_capture result."""
    record = SourceRawRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        step_id=step_id,
        adapter_name=adapter_name,
        payload_json=payload_json,
        source_domain=source_domain,
        http_status_code=http_status_code,
        http_meta_json=http_meta_json,
        content_hash=content_hash,
    )
    db.add(record)
    await db.flush()
    return record


async def store_parsed_record(
    db: AsyncSession,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    raw_record_id: uuid.UUID,
    adapter_name: str,
    parsed_json: Optional[Dict[str, Any]] = None,
    completeness_score: Optional[float] = None,
    confidence_score: Optional[float] = None,
    missing_fields: Optional[List[str]] = None,
    field_presence_json: Optional[Dict[str, bool]] = None,
) -> SourceParsedRecord:
    """Store a parsed data_capture result."""
    record = SourceParsedRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        step_id=step_id,
        raw_record_id=raw_record_id,
        adapter_name=adapter_name,
        parsed_json=parsed_json,
        completeness_score=completeness_score,
        confidence_score=confidence_score,
        missing_fields=missing_fields,
        field_presence_json=field_presence_json,
    )
    db.add(record)
    await db.flush()
    return record
