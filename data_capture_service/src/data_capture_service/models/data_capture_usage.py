"""
DataCaptureUsage model — cost and usage tracking for data_capture operations.
"""

import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class DataCaptureUsage(Base, SuperIdMixin):
    """Cost and usage tracking for each adapter operation."""

    __tablename__ = "data_capture_usage"

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
        nullable=True,
        index=True,
    )
    adapter_name = Column(String(128), nullable=False)
    operation = Column(String(256), nullable=False)
    credits_used = Column(Float, nullable=True, default=0.0)
    request_count = Column(Integer, nullable=True, default=0)
    response_bytes = Column(Integer, nullable=True, default=0)
    metadata_json = Column(JSONB, nullable=True)

    # Relationships
    run = relationship("DataCaptureRun", back_populates="usage_records")
    step = relationship("DataCaptureRunStep", back_populates="usage_records")
