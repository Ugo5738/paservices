"""
Pydantic schemas for the SuperID Metadata store API.

See docs/superid_principles.md section 5 and
docs/superid_data_capture_design.md section 3.2.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Activity records
# ---------------------------------------------------------------------------


class ActivityRecordCreate(BaseModel):
    """Body for POST /activity_records."""

    super_id: UUID = Field(..., description="The SuperID this activity is about.")
    used_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description=(
            "The service or workflow that used the SuperID "
            '(e.g. "coded_fetcher_service", "wf_dc_1_main").'
        ),
    )
    source: str = Field(
        ...,
        min_length=1,
        description=(
            "Descriptive slash-path describing what this use represents "
            '(e.g. "wf_dc_a_cf/service_invocation").'
        ),
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional contextual metadata.",
    )


class ActivityRecordResponse(BaseModel):
    """Response shape for an activity record."""

    activity_id: UUID
    super_id: UUID
    used_by: str
    used_at: datetime
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ActivityRecordList(BaseModel):
    """Response shape for GET /super_ids/{super_id}/activity_records."""

    super_id: UUID
    count: int
    items: List[ActivityRecordResponse]


# ---------------------------------------------------------------------------
# Link records
# ---------------------------------------------------------------------------


class LinkRecordCreate(BaseModel):
    """Body for POST /link_records."""

    super_id_a: UUID = Field(
        ...,
        description=(
            "One of the two SuperIDs being linked. Order is not semantically "
            "meaningful."
        ),
    )
    super_id_b: UUID = Field(
        ...,
        description=(
            "The other SuperID being linked. Order is not semantically "
            "meaningful."
        ),
    )
    created_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="The service or workflow recording the link.",
    )
    source: str = Field(
        ...,
        min_length=1,
        description=(
            "Descriptive slash-path describing why the link is claimed "
            '(e.g. "ai_fetcher_service/validates_prior_service_run").'
        ),
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional contextual metadata.",
    )

    @field_validator("super_id_b")
    @classmethod
    def _disallow_self_link(cls, super_id_b: UUID, info: Any) -> UUID:
        """A SuperID cannot be linked to itself — that's a no-op claim."""
        super_id_a = info.data.get("super_id_a")
        if super_id_a is not None and super_id_a == super_id_b:
            raise ValueError(
                "super_id_a and super_id_b must be different; a SuperID "
                "cannot be linked to itself."
            )
        return super_id_b


class LinkRecordResponse(BaseModel):
    """Response shape for a link record."""

    link_id: UUID
    super_id_a: UUID
    super_id_b: UUID
    created_at: datetime
    created_by: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class LinkRecordList(BaseModel):
    """
    Response shape for GET /super_ids/{super_id}/link_records.

    Each item includes the *other* SuperID alongside the relationship
    metadata, so consumers don't need to know which column matched.
    """

    super_id: UUID
    count: int
    items: List[LinkRecordResponse]
