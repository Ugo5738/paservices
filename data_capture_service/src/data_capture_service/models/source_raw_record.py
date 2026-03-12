"""
SourceRawRecord model — append-only raw payload storage.
"""

import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class SourceRawRecord(Base, SuperIdMixin):
    """Append-only raw payload from each adapter/baseline fetch."""

    __tablename__ = "source_raw_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.data_capture_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.data_capture_run_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adapter_name = Column(String(128), nullable=False)
    source_domain = Column(String(512), nullable=True)
    payload_json = Column(JSONB, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    http_meta_json = Column(JSONB, nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256

    # Relationships
    run = relationship("DataCaptureRun", back_populates="raw_records")
    step = relationship("DataCaptureRunStep", back_populates="raw_records")
    parsed_records = relationship(
        "SourceParsedRecord", back_populates="raw_record", cascade="all, delete-orphan"
    )
