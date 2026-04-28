"""
Fetcher registry model.

A Fetcher is one callable scraper endpoint — either a Motie-built deployed
route, or an external HTTP service we proxy to (e.g. data_capture_rightmove_service).

n8n workflows query this registry via /fetchers/lookup to decide how to capture
data for a given URL.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from data_capture_service.models.base import Base


class Fetcher(Base):
    """
    Registry of all callable scraper fetchers.

    `source_type='motie'` rows reference a MotieScraperProject (which holds the
    deployed api_url) and identify a specific deployed route on that project.

    `source_type='proxy'` rows store the api_url directly via api_url_override —
    used to wrap external services (e.g. data_capture_rightmove_service) so n8n
    can treat them uniformly.
    """

    __tablename__ = "fetchers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(512), nullable=False)
    source_type = Column(String(32), nullable=False)  # 'motie' | 'proxy'
    motie_project_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.motie_scraper_projects.id",
            name="fk_fetchers_motie_project_uuid",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    route_path = Column(String(512), nullable=False)
    http_method = Column(String(16), nullable=False, default="GET")
    # param_schema example: {"url_param": "listing_url", "url_location": "query"}
    param_schema = Column(JSONB, nullable=False, default=dict)
    api_url_override = Column(String(2048), nullable=True)
    is_metered = Column(Boolean, nullable=False, default=False)
    status = Column(
        String(32), nullable=False, default="active"
    )  # 'active' | 'disabled'
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_fetchers_domain", "domain"),
        Index("ix_fetchers_source_type", "source_type"),
        Index("ix_fetchers_status_domain", "status", "domain"),
        CheckConstraint(
            "source_type IN ('motie', 'proxy')", name="ck_fetchers_source_type"
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_fetchers_status"),
        CheckConstraint(
            "(source_type = 'motie' AND motie_project_uuid IS NOT NULL) "
            "OR (source_type = 'proxy' AND api_url_override IS NOT NULL)",
            name="ck_fetchers_source_consistency",
        ),
        {"schema": "data_capture"},
    )

    def __repr__(self) -> str:
        return (
            f"<Fetcher(domain='{self.domain}', source_type='{self.source_type}', "
            f"route='{self.route_path}', status='{self.status}')>"
        )
