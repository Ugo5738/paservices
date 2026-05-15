"""
SQLAlchemy models for the Data Capture Service.

Import all models here so Alembic can discover them for autogenerate.
"""

from data_capture_service.models.ai_fetcher import AIFetcher
from data_capture_service.models.base import Base, SuperIdMixin
from data_capture_service.models.build_flag import BuildFlag
from data_capture_service.models.canonical_media import CanonicalMedia, MediaType
from data_capture_service.models.canonical_property_snapshot import (
    CanonicalPropertySnapshot,
)
from data_capture_service.models.data_capture_run import (
    DataCaptureRun,
    DataCaptureRunMode,
    DataCaptureRunStatus,
)
from data_capture_service.models.data_capture_run_step import (
    DataCaptureRunStep,
    StepStatus,
    StepType,
)
from data_capture_service.models.data_capture_usage import DataCaptureUsage
from data_capture_service.models.fetcher import Fetcher
from data_capture_service.models.fetcher_run import (
    FetcherRun,
    FetcherRunKind,  # deprecated alias for FetcherType (chunk 6 — kept for back-compat)
    FetcherType,
)
from data_capture_service.models.motie_build import (
    MotieBuild,
    MotieBuildPromptKind,
    MotieBuildState,
    TERMINAL_BUILD_STATES,
)
from data_capture_service.models.motie_scraper_project import MotieScraperProject
from data_capture_service.models.provider_data_capture import ProviderDataCapture
from data_capture_service.models.source_parsed_record import SourceParsedRecord
from data_capture_service.models.source_raw_record import SourceRawRecord

__all__ = [
    "Base",
    "SuperIdMixin",
    "AIFetcher",
    "BuildFlag",
    "DataCaptureRun",
    "DataCaptureRunStatus",
    "DataCaptureRunMode",
    "DataCaptureRunStep",
    "StepType",
    "StepStatus",
    "Fetcher",
    "FetcherRun",
    "FetcherType",
    "FetcherRunKind",  # deprecated — alias for FetcherType, will be removed
    "MotieBuild",
    "MotieBuildPromptKind",
    "MotieBuildState",
    "TERMINAL_BUILD_STATES",
    "SourceRawRecord",
    "SourceParsedRecord",
    "CanonicalPropertySnapshot",
    "CanonicalMedia",
    "MediaType",
    "ProviderDataCapture",
    "DataCaptureUsage",
    "MotieScraperProject",
]
