"""
Pydantic request/response schemas for data_capture API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# --- Enums ---


class DataCaptureStatusEnum(str, Enum):
    """Status values exposed in API responses."""

    PENDING = "pending"
    BASELINE_RUNNING = "baseline_running"
    SCRAPING = "scraping"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class StepTypeEnum(str, Enum):
    BASELINE = "baseline"
    DATA_CAPTURE = "data_capture"
    VALIDATION = "validation"


class StepStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Request Schemas ---


class DataCaptureStartRequest(BaseModel):
    """Request to start a data_capture run."""

    url: str = Field(..., description="Target URL to data_capture")
    super_id: Optional[UUID] = Field(
        None, description="Super ID for tracking. Generated if not provided."
    )
    adapter_name: Optional[str] = Field(
        None,
        description="Specific adapter to use. If None, uses orchestrated pipeline.",
    )
    callback_url: Optional[str] = Field(
        None, description="Webhook URL for completion notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata to attach to the run"
    )
    skip_baseline: bool = Field(
        False, description="Skip the Firecrawl baseline step"
    )


class AdapterDataCaptureRequest(BaseModel):
    """Request for a direct per-adapter data_capture."""

    url: str = Field(..., description="Target URL to data_capture")
    super_id: Optional[UUID] = Field(
        None, description="Super ID for tracking. Generated if not provided."
    )
    callback_url: Optional[str] = Field(
        None, description="Webhook URL for completion notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata to attach to the run"
    )


# --- Response Schemas ---


class DataCaptureStartResponse(BaseModel):
    """Response after starting a data_capture run."""

    run_id: UUID = Field(..., description="Unique ID for this data_capture run")
    super_id: UUID = Field(..., description="Super ID for tracking")
    status: DataCaptureStatusEnum = Field(..., description="Current run status")
    poll_url: str = Field(..., description="URL to poll for status updates")
    message: str = Field("DataCapture run started", description="Human-readable message")


class StepInfo(BaseModel):
    """Summary of a single pipeline step."""

    step_order: int
    adapter_name: str
    step_type: StepTypeEnum
    status: StepStatusEnum
    completeness_score: Optional[float] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    provider_run_id: Optional[str] = None


class DataCaptureRunStatusResponse(BaseModel):
    """Response for polling run status."""

    run_id: UUID
    super_id: UUID
    status: DataCaptureStatusEnum
    target_url: str
    target_domain: str
    selected_adapter: Optional[str] = None
    completeness_score: Optional[float] = None
    fallback_count: int = 0
    error_message: Optional[str] = None
    steps: List[StepInfo] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class MediaItem(BaseModel):
    """A single media asset (image, floorplan, etc.)."""

    media_type: str
    url: str
    caption: Optional[str] = None
    sort_order: int = 0
    is_high_res: bool = False
    width: Optional[int] = None
    height: Optional[int] = None


class QualityReport(BaseModel):
    """Quality metrics for the data_capture result."""

    completeness_score: float
    priority_scores: Dict[int, float] = Field(default_factory=dict)
    fields_present: int = 0
    fields_total: int = 0
    missing_p0_fields: List[str] = Field(default_factory=list)
    baseline_available: bool = False
    validation_passed: Optional[bool] = None


class CanonicalSnapshotResponse(BaseModel):
    """The canonical property data extracted from scraping."""

    # Priority 0
    address_road: Optional[str] = None
    price: Optional[str] = None
    price_text: Optional[str] = None
    source_url: Optional[str] = None

    # Priority 1
    address_town: Optional[str] = None
    bedrooms: Optional[int] = None
    estate_agent_name: Optional[str] = None

    # Priority 2
    agent_address: Optional[str] = None
    transaction_type: Optional[str] = None
    bathrooms: Optional[int] = None
    property_type: Optional[str] = None

    # Priority 3
    full_address: Optional[str] = None
    postcode: Optional[str] = None
    description: Optional[str] = None
    rightmove_url: Optional[str] = None

    # Priority 4+ extras
    extras: Optional[Dict[str, Any]] = None


class DataCaptureResultResponse(BaseModel):
    """Full data_capture result including canonical data, media, and quality report."""

    run_id: UUID
    super_id: UUID
    status: DataCaptureStatusEnum
    source_adapter: str
    canonical: CanonicalSnapshotResponse
    media: List[MediaItem] = Field(default_factory=list)
    quality: QualityReport
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class AdapterInfo(BaseModel):
    """Information about a registered data_capture adapter."""

    name: str
    display_name: str
    provider_type: str
    supported_domains: Optional[List[str]] = None
    is_enabled: bool = True
    priority: int = 0


class AdapterRegistryResponse(BaseModel):
    """Response listing all registered adapters."""

    adapters: List[AdapterInfo] = Field(default_factory=list)
    total: int = 0
