"""
SQLAlchemy models for the Data Capture Service.

Import all models here so Alembic can discover them for autogenerate.
"""

from data_capture_service.models.base import Base, SuperIdMixin
from data_capture_service.models.canonical_media import CanonicalMedia, MediaType
from data_capture_service.models.canonical_property_snapshot import (
    CanonicalPropertySnapshot,
)
from data_capture_service.models.provider_data_capture import ProviderDataCapture
from data_capture_service.models.data_capture_run import DataCaptureRun, DataCaptureRunMode, DataCaptureRunStatus
from data_capture_service.models.data_capture_run_step import DataCaptureRunStep, StepStatus, StepType
from data_capture_service.models.data_capture_usage import DataCaptureUsage
from data_capture_service.models.source_parsed_record import SourceParsedRecord
from data_capture_service.models.source_raw_record import SourceRawRecord

__all__ = [
    "Base",
    "SuperIdMixin",
    "DataCaptureRun",
    "DataCaptureRunStatus",
    "DataCaptureRunMode",
    "DataCaptureRunStep",
    "StepType",
    "StepStatus",
    "SourceRawRecord",
    "SourceParsedRecord",
    "CanonicalPropertySnapshot",
    "CanonicalMedia",
    "MediaType",
    "ProviderDataCapture",
    "DataCaptureUsage",
]
