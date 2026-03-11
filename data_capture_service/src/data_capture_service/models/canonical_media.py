"""
CanonicalMedia model — images, floorplans, EPCs, videos linked to a canonical snapshot.
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class MediaType(str, enum.Enum):
    """Type of media asset."""

    PHOTO = "photo"
    FLOORPLAN = "floorplan"
    EPC = "epc"
    VIDEO = "video"


class CanonicalMedia(Base, SuperIdMixin):
    """Images, floorplans, and other media linked to a canonical property snapshot."""

    __tablename__ = "canonical_media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.canonical_property_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_type = Column(
        String(32),
        nullable=False,
        default=MediaType.PHOTO.value,
    )
    url = Column(String(2048), nullable=False)
    caption = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_high_res = Column(Boolean, nullable=False, default=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Relationships
    snapshot = relationship("CanonicalPropertySnapshot", back_populates="media")
