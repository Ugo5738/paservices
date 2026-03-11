"""
CanonicalPropertySnapshot model — stable downstream contract for property data.
Priority 0-3 fields as real columns, Priority 4+ in extras_json.
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    ForeignKey,
    Integer,
    Sequence,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin

# Sequence for canonical snapshot ordering
snapshot_seq = Sequence("canonical_snapshot_id_seq", schema="data_capture")


class CanonicalPropertySnapshot(Base, SuperIdMixin):
    """
    Stable downstream contract for data_captured property data.

    Priority 0-3 fields are stored as real columns for fast querying.
    Priority 4+ fields are stored in extras_json.
    """

    __tablename__ = "canonical_property_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.data_capture_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_id = Column(
        BigInteger, snapshot_seq, server_default=snapshot_seq.next_value()
    )

    # Source metadata
    source_adapter = Column(String(128), nullable=False)
    source_url = Column(String(2048), nullable=False)
    completeness_score = Column(Float, nullable=True)

    # --- Priority 0: Essential ---
    address_road = Column(String(512), nullable=True)
    price = Column(String(128), nullable=True)
    price_text = Column(String(256), nullable=True)
    # image_urls and floorplan_urls stored in canonical_media table

    # --- Priority 1: Very High ---
    address_town = Column(String(256), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    estate_agent_name = Column(String(512), nullable=True)

    # --- Priority 2: High ---
    agent_address = Column(Text, nullable=True)
    transaction_type = Column(String(64), nullable=True)
    bathrooms = Column(Integer, nullable=True)
    property_type = Column(String(128), nullable=True)

    # --- Priority 3: Medium ---
    full_address = Column(Text, nullable=True)
    postcode = Column(String(16), nullable=True)
    description = Column(Text, nullable=True)
    rightmove_url = Column(String(2048), nullable=True)

    # --- Priority 4+ stored in extras ---
    extras_json = Column(JSONB, nullable=True)

    # Relationships
    run = relationship("DataCaptureRun", back_populates="canonical_snapshot")
    media = relationship(
        "CanonicalMedia", back_populates="snapshot", cascade="all, delete-orphan"
    )
