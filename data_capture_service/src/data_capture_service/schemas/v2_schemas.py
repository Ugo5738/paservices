"""
Pydantic schemas for V2 primitive endpoints (lookup, run, validate, AI fetcher,
fetcher-builds).

These are the n8n-facing surfaces. Keep the contract narrow: every endpoint
takes/returns plain JSON with no opinion about what to do next.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# /fetchers/lookup
# ─────────────────────────────────────────────────────────────────────────────


class FetcherLookupRequest(BaseModel):
    url: str = Field(..., description="Property URL whose domain to look up")


class FetcherInfo(BaseModel):
    id: UUID
    domain: str
    source_type: str  # 'motie' | 'proxy'
    route_path: str
    http_method: str
    api_url: Optional[str] = None
    param_schema: Dict[str, Any] = Field(default_factory=dict)
    is_metered: bool = False
    status: str = "active"
    motie_project_uuid: Optional[UUID] = None


class FetcherLookupResponse(BaseModel):
    domain: str
    found: bool
    fetcher: Optional[FetcherInfo] = None


# ─────────────────────────────────────────────────────────────────────────────
# /fetchers/run
# ─────────────────────────────────────────────────────────────────────────────


class FetcherRunRequest(BaseModel):
    fetcher_id: UUID
    url: str
    extra_params: Optional[Dict[str, Any]] = None
    timeout: float = Field(default=60.0, gt=0)


class FetcherRunResponse(BaseModel):
    fetcher_id: UUID
    url: str
    status: str  # 'success' | 'http_error' | 'no_url' | 'exception'
    http_status_code: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    is_metered: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# /fetchers/validate
# ─────────────────────────────────────────────────────────────────────────────


class FetcherValidateRequest(BaseModel):
    url: str
    fetcher_id: Optional[UUID] = Field(
        default=None,
        description="Optional — for logging. Validation is data-driven, not fetcher-driven.",
    )
    fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Pre-extracted structured fields to validate. If omitted, "
        "you must provide raw_payload and a parser will be selected.",
    )
    raw_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw fetcher output (e.g. /fetchers/run payload). Will be "
        "parsed by the matching adapter if `fields` is not provided.",
    )
    adapter_name: Optional[str] = Field(
        default=None,
        description="Hint for which adapter parsed this — informs parser selection. "
        "Defaults to 'motie' when raw_payload is supplied without an adapter hint.",
    )


class FetcherValidateResponse(BaseModel):
    passed: bool
    completeness_score: float
    fields_present: int
    fields_total: int
    priority_scores: Dict[int, float] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    missing_critical_fields: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# /ai-fetchers/{adapter}/run
# ─────────────────────────────────────────────────────────────────────────────


class AIFetcherRunRequest(BaseModel):
    url: str
    super_id: Optional[UUID] = None
    prompt: Optional[str] = Field(
        default=None,
        description="Optional prompt override. Adapters may ignore if not supported.",
    )
    schema_hint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional schema/field hint for adapters that accept one (future).",
    )


class AIFetcherRunResponse(BaseModel):
    adapter: str
    url: str
    status: str  # 'success' | 'partial' | 'failed' | 'timeout'
    payload: Optional[Dict[str, Any]] = None
    fields: Optional[Dict[str, Any]] = None
    field_presence: Optional[Dict[str, bool]] = None
    missing_fields: List[str] = Field(default_factory=list)
    completeness_score: Optional[float] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# /fetcher-builds/motie/*
# ─────────────────────────────────────────────────────────────────────────────


class MotieBuildRequest(BaseModel):
    url: str
    domain: Optional[str] = Field(
        default=None,
        description="Domain to attribute the build to. If omitted, derived from url.",
    )
    prompt_kind: str = Field(
        default="build",
        description="'build' (initial) or 'repair'. Repair targets an existing project.",
    )
    failing_error: Optional[str] = Field(
        default=None, description="Required when prompt_kind='repair'."
    )
    benchmark_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Reference data from the AI fetcher to seed the build prompt.",
    )
    extra_prompt_context: Optional[str] = None


class MotieBuildResponse(BaseModel):
    project_uuid: UUID  # Our internal MotieScraperProject.id
    motie_project_id: str  # Motie's project id
    session_id: str
    status: str
    created_new_project: bool


class MotieSessionStatusResponse(BaseModel):
    session_id: str
    status: str  # 'running' | 'completed' | 'failed'
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class MotieDeployRequest(BaseModel):
    project_uuid: UUID  # Our internal MotieScraperProject.id


class MotieDeployResponse(BaseModel):
    project_uuid: UUID
    motie_project_id: str
    deployment_id: str
    status: str  # 'pending' | 'deploying' | 'deployed' | 'failed'
    api_url: Optional[str] = None


class MotieDeploymentStatusResponse(BaseModel):
    deployment_id: str
    project_id: str
    status: str
    api_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class MotiePublishRequest(BaseModel):
    project_uuid: UUID  # Our internal MotieScraperProject.id
    domain: Optional[str] = Field(
        default=None,
        description="Override the domain to register fetchers under. "
        "If omitted, uses the project's stored domain.",
    )
    is_metered: bool = False


class MotiePublishedFetcher(BaseModel):
    fetcher_id: UUID
    domain: str
    route_path: str
    http_method: str
    param_schema: Dict[str, Any]


class MotiePublishResponse(BaseModel):
    project_uuid: UUID
    motie_project_id: str
    api_url: str
    fetchers: List[MotiePublishedFetcher]


class MotieProjectStatusResponse(BaseModel):
    project_uuid: UUID
    motie_project_id: str
    domain: str
    api_url: Optional[str] = None
    deployment_status: Optional[str] = None
    last_session_id: Optional[str] = None
    last_deployment_id: Optional[str] = None
    motie_agent_status: Optional[str] = None
    motie_active_session_id: Optional[str] = None
    is_active: bool


# ─────────────────────────────────────────────────────────────────────────────
# /build-flags
# ─────────────────────────────────────────────────────────────────────────────


class BuildFlagCreateRequest(BaseModel):
    url: str
    domain: Optional[str] = None
    reason: Optional[str] = None


class BuildFlagInfo(BaseModel):
    id: UUID
    url: str
    domain: str
    reason: Optional[str] = None
    status: str
    attempts: int
    error: Optional[str] = None
    created_at: datetime
    picked_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BuildFlagListResponse(BaseModel):
    flags: List[BuildFlagInfo]
    total: int


class BuildFlagPickResponse(BaseModel):
    flag: Optional[BuildFlagInfo] = None
    picked: bool
