"""
CRUD operations for the Fetcher registry.

The registry holds one row per callable scraper endpoint (Motie-built or
external proxy). n8n hits these via /fetchers/lookup → /fetchers/run.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.fetcher import Fetcher
from data_capture_service.models.motie_scraper_project import MotieScraperProject

logger = logging.getLogger(__name__)


async def get_active_by_domain(db: AsyncSession, domain: str) -> List[Fetcher]:
    """Return all active fetchers for a domain, ordered by created_at."""
    result = await db.execute(
        select(Fetcher)
        .where(
            Fetcher.domain == domain,
            Fetcher.status == "active",
        )
        .order_by(Fetcher.created_at.asc())
    )
    return list(result.scalars().all())


async def get_first_active_by_domain(
    db: AsyncSession, domain: str
) -> Optional[Fetcher]:
    """Return the first active fetcher for a domain (used for single-fetcher MVP)."""
    fetchers = await get_active_by_domain(db, domain)
    return fetchers[0] if fetchers else None


async def get_by_id(db: AsyncSession, fetcher_id: UUID) -> Optional[Fetcher]:
    result = await db.execute(select(Fetcher).where(Fetcher.id == fetcher_id))
    return result.scalars().first()


async def resolve_api_url(db: AsyncSession, fetcher: Fetcher) -> Optional[str]:
    """
    Resolve the api_url for a fetcher.

    For source_type='proxy' we return api_url_override directly.
    For source_type='motie' we look up the linked MotieScraperProject and
    return its current api_url (which may have changed on redeploy).
    """
    if fetcher.source_type == "proxy":
        return fetcher.api_url_override

    if fetcher.source_type == "motie" and fetcher.motie_project_uuid:
        result = await db.execute(
            select(MotieScraperProject).where(
                MotieScraperProject.id == fetcher.motie_project_uuid
            )
        )
        project = result.scalars().first()
        if project:
            return project.api_url

    return None


async def create_motie_fetcher(
    db: AsyncSession,
    domain: str,
    motie_project_uuid: UUID,
    route_path: str,
    http_method: str = "GET",
    param_schema: Optional[Dict[str, Any]] = None,
    is_metered: bool = False,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Fetcher:
    """Register a fetcher backed by a Motie-deployed route."""
    fetcher = Fetcher(
        domain=domain,
        source_type="motie",
        motie_project_uuid=motie_project_uuid,
        route_path=route_path,
        http_method=http_method,
        param_schema=param_schema
        or {"url_param": "listing_url", "url_location": "query"},
        is_metered=is_metered,
        metadata_json=metadata_json,
    )
    db.add(fetcher)
    await db.flush()
    await db.refresh(fetcher)
    logger.info(
        f"Registered Motie fetcher: domain={domain}, route={route_path}, id={fetcher.id}"
    )
    return fetcher


async def create_proxy_fetcher(
    db: AsyncSession,
    domain: str,
    api_url_override: str,
    route_path: str,
    http_method: str = "POST",
    param_schema: Optional[Dict[str, Any]] = None,
    is_metered: bool = False,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Fetcher:
    """Register a fetcher that proxies to an external HTTP service."""
    fetcher = Fetcher(
        domain=domain,
        source_type="proxy",
        api_url_override=api_url_override,
        route_path=route_path,
        http_method=http_method,
        param_schema=param_schema or {"url_param": "url", "url_location": "body"},
        is_metered=is_metered,
        metadata_json=metadata_json,
    )
    db.add(fetcher)
    await db.flush()
    await db.refresh(fetcher)
    logger.info(
        f"Registered proxy fetcher: domain={domain}, "
        f"target={api_url_override}{route_path}, id={fetcher.id}"
    )
    return fetcher


async def upsert_motie_fetcher(
    db: AsyncSession,
    domain: str,
    motie_project_uuid: UUID,
    route_path: str,
    http_method: str = "GET",
    param_schema: Optional[Dict[str, Any]] = None,
    is_metered: bool = False,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Fetcher:
    """
    Insert a Motie fetcher row, or update the existing one for this
    (project, route) pair.

    Used by /fetcher-builds/motie/publish after a successful deploy.
    """
    result = await db.execute(
        select(Fetcher).where(
            Fetcher.motie_project_uuid == motie_project_uuid,
            Fetcher.route_path == route_path,
        )
    )
    existing = result.scalars().first()

    if existing:
        existing.domain = domain
        existing.http_method = http_method
        if param_schema is not None:
            existing.param_schema = param_schema
        existing.is_metered = is_metered
        if metadata_json is not None:
            existing.metadata_json = metadata_json
        existing.status = "active"
        await db.flush()
        await db.refresh(existing)
        logger.info(
            f"Updated Motie fetcher: domain={domain}, route={route_path}, id={existing.id}"
        )
        return existing

    return await create_motie_fetcher(
        db=db,
        domain=domain,
        motie_project_uuid=motie_project_uuid,
        route_path=route_path,
        http_method=http_method,
        param_schema=param_schema,
        is_metered=is_metered,
        metadata_json=metadata_json,
    )


async def disable(db: AsyncSession, fetcher_id: UUID) -> None:
    await db.execute(
        update(Fetcher).where(Fetcher.id == fetcher_id).values(status="disabled")
    )
    await db.flush()
    logger.info(f"Disabled fetcher {fetcher_id}")
