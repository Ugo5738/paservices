"""
LinkRecord model — SuperID Metadata store.

One row per claimed relationship between two SuperIDs. Append-only and
immutable (enforced by a database trigger; see migration 674e901b2bd1).
Bidirectional — the order of `super_id_a` and `super_id_b` is NOT
semantically meaningful. Queries for "give me all links involving X"
must check both columns.

See docs/superid_principles.md section 5 and
docs/superid_data_capture_design.md section 3.2.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Reuse the same Base as the existing GeneratedSuperID model so the Alembic
# env picks up all models from one metadata target.
from .generated_super_id import Base


class LinkRecord(Base):
    """
    Records that two SuperIDs are related, with descriptive metadata about
    why the relationship is being claimed.

    Bidirectional: neither side is privileged. The relationship metadata
    (the `source` field plus optional `link_metadata`) describes the *act
    of claiming* the link — when it happened, what claimed it, and the
    descriptive intent (e.g. "ai_fetcher_service/validates_prior_service_run").

    No structural hierarchy between SuperIDs is implied. See
    docs/superid_principles.md section 8 (decision heuristics) and section 9
    (mistake "introducing hierarchy to represent multi-shot iterations").
    """

    __tablename__ = "link_records"

    link_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    super_id_a = Column(UUID(as_uuid=True), nullable=False, index=True)
    super_id_b = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(String(128), nullable=False)
    source = Column(Text, nullable=False)
    # Renamed to `link_metadata` to avoid SQLAlchemy's reserved `metadata`
    # attribute on declarative models — same pattern as GeneratedSuperID.
    link_metadata = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return (
            f"<LinkRecord(link_id={self.link_id}, "
            f"super_id_a={self.super_id_a}, super_id_b={self.super_id_b}, "
            f"created_by='{self.created_by}', created_at={self.created_at})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model instance to a dictionary."""
        return {
            "link_id": str(self.link_id),
            "super_id_a": str(self.super_id_a),
            "super_id_b": str(self.super_id_b),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "source": self.source,
            "metadata": self.link_metadata,
        }
