"""
Base adapter protocol and shared data types for the data_capture adapter architecture.

All data_capture adapters must implement the DataCaptureAdapter protocol.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class AdapterStatus(str, Enum):
    """Status of an adapter operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class DataCaptureRequest:
    """Input to an adapter's fetch_raw method."""

    url: str
    super_id: Optional[str] = None
    adapter_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RawDataCaptureResult:
    """Output from an adapter's fetch_raw method — raw untransformed data."""

    adapter_name: str
    url: str
    status: AdapterStatus
    payload: Optional[Dict[str, Any]] = None
    markdown: Optional[str] = None
    html: Optional[str] = None
    http_status_code: Optional[int] = None
    http_meta: Optional[Dict[str, Any]] = None
    content_hash: Optional[str] = None
    provider_run_id: Optional[str] = None  # e.g. Motie sessionId
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class ParsedDataCaptureResult:
    """Output from an adapter's parse method — structured fields extracted from raw data."""

    adapter_name: str
    url: str
    status: AdapterStatus
    fields: Dict[str, Any] = field(default_factory=dict)
    field_presence: Dict[str, bool] = field(default_factory=dict)
    image_urls: List[str] = field(default_factory=list)
    floorplan_urls: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class CompletenessScore:
    """Result from an adapter's score method."""

    overall: float  # 0.0 to 1.0
    priority_scores: Dict[int, float] = field(default_factory=dict)  # {0: 0.8, 1: 0.5, ...}
    fields_present: int = 0
    fields_total: int = 0
    details: Optional[Dict[str, Any]] = None


@dataclass
class BaselineResult:
    """Output from the Firecrawl baseline provider."""

    url: str
    status: AdapterStatus
    markdown: Optional[str] = None
    field_presence: Dict[str, bool] = field(default_factory=dict)
    image_count: int = 0
    has_price: bool = False
    has_address: bool = False
    has_floorplan: bool = False
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    credits_used: int = 0


@runtime_checkable
class DataCaptureAdapter(Protocol):
    """
    Protocol that all data_capture adapters must implement.

    Each adapter is responsible for:
    1. fetch_raw: Retrieving raw data from a source (HTTP, API, etc.)
    2. parse: Extracting structured fields from raw data
    3. score: Computing a completeness score for the parsed result
    """

    name: str
    supported_domains: List[str]

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """Fetch raw data from the target URL."""
        ...

    async def parse(self, raw: RawDataCaptureResult) -> ParsedDataCaptureResult:
        """Parse raw data into structured fields."""
        ...

    async def score(self, parsed: ParsedDataCaptureResult) -> CompletenessScore:
        """Compute completeness score for the parsed result."""
        ...
