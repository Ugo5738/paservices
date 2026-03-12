"""
DataCaptureRunStep model — one row per adapter attempt within a data_capture run.
"""

import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class StepType(str, enum.Enum):
    """Type of step in the data_capture pipeline."""

    BASELINE = "baseline"
    DATA_CAPTURE = "data_capture"
    VALIDATION = "validation"


class StepStatus(str, enum.Enum):
    """Status of an individual step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DataCaptureRunStep(Base, SuperIdMixin):
    """One row per adapter attempt within a data_capture run."""

    __tablename__ = "data_capture_run_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_capture.data_capture_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order = Column(Integer, nullable=False)
    adapter_name = Column(String(128), nullable=False)
    step_type = Column(
        Enum(StepType, name="step_type", schema="data_capture"),
        nullable=False,
    )
    provider_type = Column(String(128), nullable=True)
    status = Column(
        Enum(StepStatus, name="step_status", schema="data_capture"),
        nullable=False,
        default=StepStatus.PENDING,
    )
    completeness_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    provider_run_id = Column(String(512), nullable=True)  # e.g. Motie sessionId
    metadata_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    run = relationship("DataCaptureRun", back_populates="steps")
    raw_records = relationship(
        "SourceRawRecord", back_populates="step", cascade="all, delete-orphan"
    )
    parsed_records = relationship(
        "SourceParsedRecord", back_populates="step", cascade="all, delete-orphan"
    )
    usage_records = relationship(
        "DataCaptureUsage", back_populates="step", cascade="all, delete-orphan"
    )
