"""
CRUD operations for the AIFetcher registry.

The registry is the source of truth for which AI fetcher adapters exist and
which one is the default baseline (used by W3 scoring). The router/services
layer only knows how to look up rows by name or by-default-baseline; it never
hardcodes vendor names.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.ai_fetcher import AIFetcher

logger = logging.getLogger(__name__)


async def get_by_name(db: AsyncSession, name: str) -> Optional[AIFetcher]:
    result = await db.execute(select(AIFetcher).where(AIFetcher.name == name))
    return result.scalars().first()


async def get_by_id(db: AsyncSession, ai_fetcher_id: UUID) -> Optional[AIFetcher]:
    result = await db.execute(select(AIFetcher).where(AIFetcher.id == ai_fetcher_id))
    return result.scalars().first()


async def list_enabled(db: AsyncSession) -> List[AIFetcher]:
    """Return all enabled AI fetchers ordered by priority (lowest first)"""
    result = await db.execute(
        select(AIFetcher)
        .where(AIFetcher.enabled.is_(True))
        .order_by(AIFetcher.priority.asc(), AIFetcher.name.asc())
    )
    return list(result.scalars().all())


async def get_default_baseline(db: AsyncSession) -> Optional[AIFetcher]:
    """
    Return the AI fetcher flagged as the default baseline.

    Used by W3 scoring to know which AI fetcher to call for the build-time
    benchmark — vendor-agnostic by design (today=Firecrawl, future=AI Council).
    """
    result = await db.execute(
        select(AIFetcher).where(
            AIFetcher.is_default_baseline.is_(True),
            AIFetcher.enabled.is_(True),
        )
    )
    row = result.scalars().first()
    if row is None:
        # Fallback: highest-priority enabled adapter.
        enabled = await list_enabled(db)
        if enabled:
            logger.warning(
                "No is_default_baseline=true AI fetcher; falling back to "
                f"highest-priority enabled adapter: {enabled[0].name}"
            )
            return enabled[0]
    return row
