"""
V2 endpoints for the build_flags queue.

Build flags are written by parents (e.g. WF A) when a domain has no coded
fetcher and the AI fetcher path was used. Consumed by WF C — which serializes
build runs per-domain and never blocks user-facing flows.

POST   /build-flags                — create a flag
GET    /build-flags                — list (filtered by status, default 'pending')
POST   /build-flags/{id}/pick      — atomic claim (pending → in_progress)
POST   /build-flags/{id}/done      — terminal success
POST   /build-flags/{id}/failed    — terminal failure with error
POST   /build-flags/{id}/reset     — return to pending (e.g. on session-lock conflict)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.crud import build_flag_crud
from data_capture_service.db import get_db
from data_capture_service.models.build_flag import BuildFlag
from data_capture_service.schemas.v2_schemas import (
    BuildFlagCreateRequest,
    BuildFlagInfo,
    BuildFlagListResponse,
    BuildFlagPickResponse,
)
from data_capture_service.utils.security import validate_token
from data_capture_service.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/build-flags",
    tags=["Build Flags V2"],
    dependencies=[Depends(validate_token)],
)


class BuildFlagFailedRequest(BaseModel):
    error: Optional[str] = None


def _to_info(flag: BuildFlag) -> BuildFlagInfo:
    return BuildFlagInfo(
        id=flag.id,
        url=flag.url,
        domain=flag.domain,
        reason=flag.reason,
        status=flag.status,
        attempts=flag.attempts,
        error=flag.error,
        created_at=flag.created_at,
        picked_at=flag.picked_at,
        completed_at=flag.completed_at,
    )


@router.post("", response_model=BuildFlagInfo, status_code=201)
async def create_flag(
    request: BuildFlagCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a build flag for a URL/domain. Idempotent at the parent level —
    callers should check for existing pending flags via has_pending_for_domain
    or just GET /build-flags?status=pending to dedupe.
    """
    domain = (request.domain or extract_domain(request.url)).lower()
    if not domain:
        raise HTTPException(400, "Could not derive domain from url")

    flag = await build_flag_crud.create(
        db=db, url=request.url, domain=domain, reason=request.reason
    )
    await db.commit()
    return _to_info(flag)


@router.get("", response_model=BuildFlagListResponse)
async def list_flags(
    status: str = Query("pending", description="pending | in_progress | done | failed"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    if status == "pending":
        flags = await build_flag_crud.list_pending(db, limit=limit)
    else:
        # Light support for other statuses via direct query.
        from sqlalchemy import select

        q = (
            select(BuildFlag)
            .where(BuildFlag.status == status)
            .order_by(BuildFlag.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(q)
        flags = list(result.scalars().all())
    return BuildFlagListResponse(flags=[_to_info(f) for f in flags], total=len(flags))


@router.post("/{flag_id}/pick", response_model=BuildFlagPickResponse)
async def pick_flag(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Move a flag from pending → in_progress (single-row claim, idempotent-ish)."""
    flag = await build_flag_crud.mark_in_progress(db, flag_id)
    await db.commit()
    if not flag or flag.status != "in_progress":
        # Already picked by someone else, or flag does not exist.
        existing = await build_flag_crud.get_by_id(db, flag_id)
        return BuildFlagPickResponse(
            flag=_to_info(existing) if existing else None, picked=False
        )
    return BuildFlagPickResponse(flag=_to_info(flag), picked=True)


@router.post("/{flag_id}/done", response_model=BuildFlagInfo)
async def mark_flag_done(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    flag = await build_flag_crud.get_by_id(db, flag_id)
    if not flag:
        raise HTTPException(404, f"build_flag {flag_id} not found")
    await build_flag_crud.mark_done(db, flag_id)
    await db.commit()
    flag = await build_flag_crud.get_by_id(db, flag_id)
    return _to_info(flag)


@router.post("/{flag_id}/failed", response_model=BuildFlagInfo)
async def mark_flag_failed(
    flag_id: UUID,
    request: BuildFlagFailedRequest,
    db: AsyncSession = Depends(get_db),
):
    flag = await build_flag_crud.get_by_id(db, flag_id)
    if not flag:
        raise HTTPException(404, f"build_flag {flag_id} not found")
    await build_flag_crud.mark_failed(db, flag_id, error=request.error)
    await db.commit()
    flag = await build_flag_crud.get_by_id(db, flag_id)
    return _to_info(flag)


@router.post("/{flag_id}/reset", response_model=BuildFlagInfo)
async def reset_flag_to_pending(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Used by WF C when a Motie session-lock conflict prevents progress this tick."""
    flag = await build_flag_crud.get_by_id(db, flag_id)
    if not flag:
        raise HTTPException(404, f"build_flag {flag_id} not found")
    await build_flag_crud.reset_to_pending(db, flag_id)
    await db.commit()
    flag = await build_flag_crud.get_by_id(db, flag_id)
    return _to_info(flag)
