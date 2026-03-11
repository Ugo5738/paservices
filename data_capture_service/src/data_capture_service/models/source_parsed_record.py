"""
SourceParsedRecord model — parsed interpretation of raw data.
"""

import uuid

from sqlalchemy import Column, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base


class SourceParsedRecord(Base):
    """Parsed interpretation of a raw record."""

    __tablename__ = "source_parsed_records"

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
    raw_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.source_raw_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    adapter_name = Column(String(128), nullable=False)
    parsed_json = Column(JSONB, nullable=True)
    completeness_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    missing_fields = Column(JSONB, nullable=True)  # List of missing field names
    field_presence_json = Column(JSONB, nullable=True)  # {field_name: bool}

    # Relationships
    run = relationship("DataCaptureRun", back_populates="parsed_records")
    step = relationship("DataCaptureRunStep", back_populates="parsed_records")
    raw_record = relationship("SourceRawRecord", back_populates="parsed_records")
