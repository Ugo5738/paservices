"""
Router for the SuperID Metadata store: activity records + link records.

Endpoints:
  POST /activity_records                           — record one use
  POST /link_records                               — record one link
  GET  /super_ids/{super_id}/activity_records      — list activity for X
  GET  /super_ids/{super_id}/link_records          — list links involving X

All endpoints are M2M-JWT-gated. Writes require the
`superid_metadata:write` permission; reads require `superid_metadata:read`.

See docs/superid_principles.md section 5 and
docs/superid_data_capture_design.md section 3.2.
"""

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.activity_record_crud import (
    create_activity_record,
    list_activity_for_super_id,
)
from ..crud.link_record_crud import create_link_record, list_links_for_super_id
from ..db import get_db
from ..dependencies import validate_token
from ..schemas.auth_schema import TokenData
from ..schemas.metadata_schema import (
    ActivityRecordCreate,
    ActivityRecordList,
    ActivityRecordResponse,
    LinkRecordCreate,
    LinkRecordList,
    LinkRecordResponse,
)
from ..utils.logging_config import logger

WRITE_PERMISSION = "superid_metadata:write"
READ_PERMISSION = "superid_metadata:read"

router = APIRouter()


def _require_permission(token_data: TokenData, required: str) -> None:
    """Raise 403 if the token does not carry the required permission."""
    if required not in (token_data.permissions or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {required}",
        )


# ---------------------------------------------------------------------------
# Writes — POST endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/activity_records",
    response_model=ActivityRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record one use of a SuperID by a service or workflow",
    description=(
        "Appends one activity record to the SuperID Metadata store. "
        "Append-only — once written, the record cannot be modified or "
        "deleted (enforced by a database trigger)."
    ),
)
async def create_activity_record_endpoint(
    request_body: ActivityRecordCreate,
    request: Request,
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> ActivityRecordResponse:
    _require_permission(token_data, WRITE_PERMISSION)
    logger.info(
        "Inbound: create activity record",
        extra={
            "request": {"method": request.method, "path": request.url.path},
            "super_id": str(request_body.super_id),
            "used_by": request_body.used_by,
            "source": request_body.source,
        },
    )
    try:
        record = await create_activity_record(
            db,
            super_id=request_body.super_id,
            used_by=request_body.used_by,
            source=request_body.source,
            metadata=request_body.metadata,
        )
        return ActivityRecordResponse(
            activity_id=record.activity_id,
            super_id=record.super_id,
            used_by=record.used_by,
            used_at=record.used_at,
            source=record.source,
            metadata=record.activity_metadata or {},
        )
    except Exception as e:
        logger.error(
            f"Error creating activity record: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record activity due to a server error.",
        )


@router.post(
    "/link_records",
    response_model=LinkRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record one claimed relationship between two SuperIDs",
    description=(
        "Appends one link record to the SuperID Metadata store. Bidirectional "
        "— the order of super_id_a / super_id_b is not semantically meaningful. "
        "Append-only — once written, the record cannot be modified or deleted "
        "(enforced by a database trigger)."
    ),
)
async def create_link_record_endpoint(
    request_body: LinkRecordCreate,
    request: Request,
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> LinkRecordResponse:
    _require_permission(token_data, WRITE_PERMISSION)
    logger.info(
        "Inbound: create link record",
        extra={
            "request": {"method": request.method, "path": request.url.path},
            "super_id_a": str(request_body.super_id_a),
            "super_id_b": str(request_body.super_id_b),
            "created_by": request_body.created_by,
            "source": request_body.source,
        },
    )
    try:
        record = await create_link_record(
            db,
            super_id_a=request_body.super_id_a,
            super_id_b=request_body.super_id_b,
            created_by=request_body.created_by,
            source=request_body.source,
            metadata=request_body.metadata,
        )
        return LinkRecordResponse(
            link_id=record.link_id,
            super_id_a=record.super_id_a,
            super_id_b=record.super_id_b,
            created_at=record.created_at,
            created_by=record.created_by,
            source=record.source,
            metadata=record.link_metadata or {},
        )
    except Exception as e:
        logger.error(f"Error creating link record: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record link due to a server error.",
        )


# ---------------------------------------------------------------------------
# Reads — GET endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/super_ids/{super_id}/activity_records",
    response_model=ActivityRecordList,
    summary="List activity records for a SuperID",
)
async def list_activity_endpoint(
    super_id: UUID,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> ActivityRecordList:
    _require_permission(token_data, READ_PERMISSION)
    records = await list_activity_for_super_id(
        db, super_id=super_id, limit=limit, offset=offset
    )
    items = [
        ActivityRecordResponse(
            activity_id=r.activity_id,
            super_id=r.super_id,
            used_by=r.used_by,
            used_at=r.used_at,
            source=r.source,
            metadata=r.activity_metadata or {},
        )
        for r in records
    ]
    return ActivityRecordList(super_id=super_id, count=len(items), items=items)


@router.get(
    "/super_ids/{super_id}/link_records",
    response_model=LinkRecordList,
    summary="List link records involving a SuperID (bidirectional)",
)
async def list_links_endpoint(
    super_id: UUID,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> LinkRecordList:
    _require_permission(token_data, READ_PERMISSION)
    records = await list_links_for_super_id(
        db, super_id=super_id, limit=limit, offset=offset
    )
    items = [
        LinkRecordResponse(
            link_id=r.link_id,
            super_id_a=r.super_id_a,
            super_id_b=r.super_id_b,
            created_at=r.created_at,
            created_by=r.created_by,
            source=r.source,
            metadata=r.link_metadata or {},
        )
        for r in records
    ]
    return LinkRecordList(super_id=super_id, count=len(items), items=items)
