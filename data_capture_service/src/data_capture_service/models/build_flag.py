"""
Build flag queue model.

Written by parents (e.g. WF A) when a domain has no coded fetcher but data was
captured via the AI fetcher path. Consumed by WF C — which serializes builds
per-domain (one Motie session per project at a time) and runs WF3.

This is the decoupling mechanism that lets WF A return immediately to the user
while a coded fetcher is built in the background, never workflow-to-workflow
triggering.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from data_capture_service.models.base import Base


class BuildFlag(Base):
    """Queue row indicating a URL/domain needs a coded fetcher built."""

    __tablename__ = "build_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String(2048), nullable=False)
    domain = Column(String(512), nullable=False)
    reason = Column(String(512), nullable=True)
    status = Column(
        String(32), nullable=False, default="pending"
    )  # 'pending' | 'in_progress' | 'done' | 'failed'
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    picked_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_build_flags_domain", "domain"),
        Index("ix_build_flags_status_created", "status", "created_at"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'done', 'failed')",
            name="ck_build_flags_status",
        ),
        {"schema": "data_capture"},
    )

    def __repr__(self) -> str:
        return (
            f"<BuildFlag(domain='{self.domain}', status='{self.status}', "
            f"attempts={self.attempts})>"
        )
