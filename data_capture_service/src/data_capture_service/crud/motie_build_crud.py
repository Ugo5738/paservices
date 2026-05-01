"""
CRUD operations for MotieBuild.

A MotieBuild row tracks one Motie build attempt (initial or repair). The
state machine is advanced by the motie_build_orchestrator service as it
polls Motie's session and deployment APIs.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.motie_build import (
    MotieBuild,
    MotieBuildPromptKind,
    MotieBuildState,
    TERMINAL_BUILD_STATES,
)

logger = logging.getLogger(__name__)


async def create(
    db: AsyncSession,
    *,
    project_uuid: UUID,
    domain: str,
    url: str,
    prompt_kind: str,
    session_id: Optional[str] = None,
    state: str = MotieBuildState.SESSION_PENDING.value,
    attempt_number: int = 1,
    parent_build_id: Optional[UUID] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> MotieBuild:
    row = MotieBuild(
        project_uuid=project_uuid,
        domain=domain,
        url=url,
        prompt_kind=prompt_kind,
        session_id=session_id,
        state=state,
        attempt_number=attempt_number,
        parent_build_id=parent_build_id,
        metadata_json=metadata_json,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_by_id(db: AsyncSession, build_id: UUID) -> Optional[MotieBuild]:
    result = await db.execute(select(MotieBuild).where(MotieBuild.id == build_id))
    return result.scalars().first()


async def get_by_session_id(
    db: AsyncSession, session_id: str
) -> Optional[MotieBuild]:
    result = await db.execute(
        select(MotieBuild).where(MotieBuild.session_id == session_id)
    )
    return result.scalars().first()


async def list_by_project(
    db: AsyncSession, project_uuid: UUID, limit: int = 50
) -> List[MotieBuild]:
    result = await db.execute(
        select(MotieBuild)
        .where(MotieBuild.project_uuid == project_uuid)
        .order_by(MotieBuild.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_state(
    db: AsyncSession,
    build_id: UUID,
    *,
    state: Optional[str] = None,
    session_id: Optional[str] = None,
    deployment_id: Optional[str] = None,
    api_url: Optional[str] = None,
    benchmark_score: Optional[float] = None,
    benchmark_diff_json: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> Optional[MotieBuild]:
    values: Dict[str, Any] = {}
    if state is not None:
        values["state"] = state
        if state in TERMINAL_BUILD_STATES:
            values["finished_at"] = datetime.now(timezone.utc)
    if session_id is not None:
        values["session_id"] = session_id
    if deployment_id is not None:
        values["deployment_id"] = deployment_id
    if api_url is not None:
        values["api_url"] = api_url
    if benchmark_score is not None:
        values["benchmark_score"] = benchmark_score
    if benchmark_diff_json is not None:
        values["benchmark_diff_json"] = benchmark_diff_json
    if error_message is not None:
        values["error_message"] = error_message

    if not values:
        return await get_by_id(db, build_id)

    await db.execute(
        update(MotieBuild).where(MotieBuild.id == build_id).values(**values)
    )
    await db.flush()
    return await get_by_id(db, build_id)


async def latest_attempt_number(
    db: AsyncSession, project_uuid: UUID
) -> int:
    """Return the largest attempt_number recorded for the project (0 if none)."""
    result = await db.execute(
        select(MotieBuild.attempt_number)
        .where(MotieBuild.project_uuid == project_uuid)
        .order_by(MotieBuild.attempt_number.desc())
        .limit(1)
    )
    n = result.scalars().first()
    return int(n) if n else 0
