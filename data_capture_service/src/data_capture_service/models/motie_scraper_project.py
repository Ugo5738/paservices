"""
Model for tracking Motie v2 scraper projects and their deployed endpoints.

Maps domains to Motie project IDs and deployed API URLs so we can route
known domains to deployed scrapers (fast, cheap) and only use the agent
for new domains or repairs.
"""

import uuid

from sqlalchemy import Boolean, Column, Index, String
from sqlalchemy.dialects.postgresql import UUID

from data_capture_service.models.base import Base


class MotieScraperProject(Base):
    """
    Tracks domain → Motie project/deployment mappings.

    When a scraper is built and deployed for a domain via Motie v2,
    we store the project_id and api_url here so future requests for
    that domain can call the deployed endpoint directly.
    """

    __tablename__ = "motie_scraper_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(512), nullable=False, unique=True, index=True)
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
