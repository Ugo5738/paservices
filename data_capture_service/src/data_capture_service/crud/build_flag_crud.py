"""
CRUD operations for the build_flags queue.

Build flags are written when WF A captures data via an AI fetcher because no
coded fetcher existed for the domain — flagging the URL/domain for later
coded-fetcher build by WF C.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.build_flag import BuildFlag

logger = logging.getLogger(__name__)


async def create(
    db: AsyncSession,
    url: str,
    domain: str,
    reason: Optional[str] = None,
) -> BuildFlag:
    """Write a new pending build flag."""
    flag = BuildFlag(url=url, domain=domain, reason=reason, status="pending")
    db.add(flag)
    await db.flush()
    await db.refresh(flag)
    logger.info(f"Created build_flag: domain={domain}, url={url}, id={flag.id}")
    return flag


async def get_by_id(db: AsyncSession, flag_id: UUID) -> Optional[BuildFlag]:
    result = await db.execute(select(BuildFlag).where(BuildFlag.id == flag_id))
    return result.scalars().first()


async def list_pending(db: AsyncSession, limit: int = 50) -> List[BuildFlag]:
    """List pending flags oldest-first (FIFO)."""
    result = await db.execute(
        select(BuildFlag)
        .where(BuildFlag.status == "pending")
        .order_by(BuildFlag.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def has_pending_for_domain(db: AsyncSession, domain: str) -> bool:
    """True if there's an existing pending or in-progress flag for this domain."""
    result = await db.execute(
        select(BuildFlag.id).where(
            BuildFlag.domain == domain,
            BuildFlag.status.in_(["pending", "in_progress"]),
        )
    )
    return result.scalars().first() is not None


async def mark_in_progress(db: AsyncSession, flag_id: UUID) -> Optional[BuildFlag]:
    await db.execute(
        update(BuildFlag)
        .where(BuildFlag.id == flag_id, BuildFlag.status == "pending")
        .values(
            status="in_progress",
            picked_at=datetime.now(timezone.utc),
            attempts=BuildFlag.attempts + 1,
        )
    )
    await db.flush()
    return await get_by_id(db, flag_id)


async def mark_done(db: AsyncSession, flag_id: UUID) -> None:
    await db.execute(
        update(BuildFlag)
        .where(BuildFlag.id == flag_id)
        .values(status="done", completed_at=datetime.now(timezone.utc), error=None)
    )
    await db.flush()
    logger.info(f"Build flag {flag_id} marked done")


async def mark_failed(
    db: AsyncSession, flag_id: UUID, error: Optional[str] = None
) -> None:
    await db.execute(
        update(BuildFlag)
        .where(BuildFlag.id == flag_id)
        .values(
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=error,
        )
    )
    await db.flush()
    logger.info(f"Build flag {flag_id} marked failed: {error}")


async def reset_to_pending(db: AsyncSession, flag_id: UUID) -> None:
    """Move a flag back to pending (e.g. after a Motie session-lock conflict)."""
    await db.execute(
        update(BuildFlag)
        .where(BuildFlag.id == flag_id)
        .values(status="pending", picked_at=None)
    )
    await db.flush()
    logger.info(f"Build flag {flag_id} reset to pending")
