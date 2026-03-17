"""
CRUD operations for MotieScraperProject.

Manages domain → Motie project/deployment mappings.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.motie_scraper_project import MotieScraperProject

logger = logging.getLogger(__name__)


async def get_by_domain(db: AsyncSession, domain: str) -> Optional[MotieScraperProject]:
    """Look up a Motie scraper project by domain."""
    result = await db.execute(
        select(MotieScraperProject).where(
            MotieScraperProject.domain == domain,
            MotieScraperProject.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().first()


async def get_by_project_id(
    db: AsyncSession, motie_project_id: str
) -> Optional[MotieScraperProject]:
    """Look up a Motie scraper project by Motie project ID."""
    result = await db.execute(
        select(MotieScraperProject).where(
            MotieScraperProject.motie_project_id == motie_project_id
        )
    )
    return result.scalars().first()


async def create(
    db: AsyncSession,
    domain: str,
    motie_project_id: str,
    motie_project_name: Optional[str] = None,
) -> MotieScraperProject:
    """Create a new Motie scraper project record."""
    project = MotieScraperProject(
        domain=domain,
        motie_project_id=motie_project_id,
        motie_project_name=motie_project_name,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    logger.info(
        f"Created MotieScraperProject: domain={domain}, "
        f"motie_project_id={motie_project_id}"
    )
    return project


async def update_deployment(
    db: AsyncSession,
    project_id: UUID,
    api_url: Optional[str] = None,
    route_path: Optional[str] = None,
    deployment_id: Optional[str] = None,
    deployment_status: Optional[str] = None,
    last_session_id: Optional[str] = None,
) -> Optional[MotieScraperProject]:
    """Update deployment info for a Motie scraper project."""
    values = {}
    if api_url is not None:
        values["api_url"] = api_url
    if route_path is not None:
        values["route_path"] = route_path
    if deployment_id is not None:
        values["last_deployment_id"] = deployment_id
    if deployment_status is not None:
        values["deployment_status"] = deployment_status
    if last_session_id is not None:
        values["last_session_id"] = last_session_id

    if not values:
        return None

    await db.execute(
        update(MotieScraperProject)
        .where(MotieScraperProject.id == project_id)
        .values(**values)
    )
    await db.flush()

    result = await db.execute(
        select(MotieScraperProject).where(MotieScraperProject.id == project_id)
    )
    project = result.scalars().first()
    logger.info(f"Updated MotieScraperProject {project_id}: {values}")
    return project


async def deactivate(db: AsyncSession, project_id: UUID) -> None:
    """Deactivate a Motie scraper project."""
    await db.execute(
        update(MotieScraperProject)
        .where(MotieScraperProject.id == project_id)
        .values(is_active=False)
    )
    await db.flush()
    logger.info(f"Deactivated MotieScraperProject {project_id}")
