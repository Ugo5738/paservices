"""
DataCaptureRun model — central audit record for each data_capture request.
"""

import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class DataCaptureRunStatus(str, enum.Enum):
    """Status lifecycle for a data_capture run."""

    PENDING = "pending"
    BASELINE_RUNNING = "baseline_running"
    SCRAPING = "scraping"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class DataCaptureRunMode(str, enum.Enum):
    """How the data_capture was initiated."""

    ORCHESTRATED = "orchestrated"  # Full pipeline with adapter chain
    DIRECT_ADAPTER = "direct_adapter"  # Specific adapter via per-adapter endpoint


class DataCaptureRun(Base, SuperIdMixin):
    """Central audit record per data_capture request."""

    __tablename__ = "data_capture_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_url = Column(String(2048), nullable=False, index=True)
    target_domain = Column(String(512), nullable=False, index=True)
    mode = Column(
        Enum(DataCaptureRunMode, name="data_capture_run_mode", schema="data_capture"),
        nullable=False,
        default=DataCaptureRunMode.ORCHESTRATED,
    )
    selected_adapter = Column(String(128), nullable=True)
    status = Column(
        Enum(DataCaptureRunStatus, name="data_capture_run_status", schema="data_capture"),
        nullable=False,
        default=DataCaptureRunStatus.PENDING,
        index=True,
    )
    completeness_score = Column(Float, nullable=True)
    fallback_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    route_decision_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    steps = relationship(
        "DataCaptureRunStep", back_populates="run", cascade="all, delete-orphan"
    )
    raw_records = relationship(
        "SourceRawRecord", back_populates="run", cascade="all, delete-orphan"
    )
    parsed_records = relationship(
        "SourceParsedRecord", back_populates="run", cascade="all, delete-orphan"
    )
    canonical_snapshot = relationship(
        "CanonicalPropertySnapshot", back_populates="run", uselist=False
    )
    usage_records = relationship(
        "DataCaptureUsage", back_populates="run", cascade="all, delete-orphan"
    )
