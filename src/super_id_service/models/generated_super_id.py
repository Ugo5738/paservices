"""
Database model for generated super IDs.

This model represents the persistent storage of all generated super IDs,
including metadata about when they were created and which client requested them.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class GeneratedSuperID(Base):
    """
    Represents a generated super ID in the system.

    Each instance tracks a unique identifier (UUID) along with metadata
    about when it was generated and which client requested it.
    """

    __tablename__ = "generated_super_ids"

    id = Column(BigInteger, primary_key=True)
    super_id = Column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4
    )
    generated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    requested_by_client_id = Column(String, nullable=True)
    super_id_metadata = Column(
        JSONB, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy reserved name conflict

    def __repr__(self):
        return f"<GeneratedSuperID(id={self.id}, super_id={self.super_id}, generated_at={self.generated_at})>"

    def to_dict(self):
        """Convert the model instance to a dictionary."""
        return {
            "id": self.id,
            "super_id": str(self.super_id),
            "generated_at": (
                self.generated_at.isoformat() if self.generated_at else None
            ),
            "requested_by_client_id": self.requested_by_client_id,
            "metadata": self.super_id_metadata,  # Still return as 'metadata' in the dict for backward compatibility
        }
