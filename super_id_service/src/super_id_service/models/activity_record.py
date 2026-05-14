"""
ActivityRecord model — SuperID Metadata store.

One row per use of a SuperID by a service or workflow. Append-only and
immutable (enforced by a database trigger; see migration 674e901b2bd1).

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


class ActivityRecord(Base):
    """
    Records that a specific service or workflow used a specific SuperID at a
    specific moment, with descriptive metadata.

    Activity records describe a single SuperID's journey: where it has been,
    when, and in what context. The collection of activity records for one
    SuperID is its complete usage history.
    """

    __tablename__ = "activity_records"

    activity_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    super_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    used_by = Column(String(128), nullable=False)
    used_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source = Column(Text, nullable=False)
    # Renamed to `activity_metadata` to avoid SQLAlchemy's reserved `metadata`
    # attribute on declarative models — same pattern as GeneratedSuperID.
    activity_metadata = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityRecord(activity_id={self.activity_id}, "
            f"super_id={self.super_id}, used_by='{self.used_by}', "
            f"used_at={self.used_at})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model instance to a dictionary."""
        return {
            "activity_id": str(self.activity_id),
            "super_id": str(self.super_id),
            "used_by": self.used_by,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "source": self.source,
            "metadata": self.activity_metadata,
        }
