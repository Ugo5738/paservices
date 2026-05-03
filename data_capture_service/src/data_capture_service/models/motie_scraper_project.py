"""
Model for tracking Motie v2 scraper projects and their deployed endpoints.

Each row is one *attempt* against a domain on Motie's side. A domain can
have many rows over time (the orchestrator spawns a fresh Motie project
when an existing one's session is busy or stuck). The "current" project
for a domain is the one whose deployment is referenced by the active
fetchers row — that mapping lives in the fetchers table, not here.
"""

import uuid

from sqlalchemy import Boolean, Column, Index, String
from sqlalchemy.dialects.postgresql import UUID

from data_capture_service.models.base import Base


class MotieScraperProject(Base):
    """
    Tracks Motie project/deployment attempts. Many rows per domain are
    allowed (e.g. when a previous project's session is stuck on Motie's
    side and we spawn a fresh one to keep building).
    """

    __tablename__ = "motie_scraper_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(512), nullable=False, index=True)
    motie_project_id = Column(String(256), nullable=False)
    motie_project_name = Column(String(512), nullable=True)
    api_url = Column(String(2048), nullable=True)
    route_path = Column(String(512), nullable=True)
    last_deployment_id = Column(String(256), nullable=True)
    deployment_status = Column(String(64), nullable=True)  # deployed, pending, failed
    last_session_id = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_motie_scraper_projects_motie_project_id", "motie_project_id"),
        {"schema": "data_capture"},
    )

    def __repr__(self) -> str:
        return (
            f"<MotieScraperProject(domain='{self.domain}', "
            f"project_id='{self.motie_project_id}', "
            f"status='{self.deployment_status}')>"
        )
