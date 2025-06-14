"""
Pydantic models (schemas) for the Super ID Service API.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SuperIdRequest(BaseModel):
    """
    Request model for generating super_ids.
    """

    count: int = Field(default=1, ge=1, le=100, description="Number of IDs to generate")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata to associate with the generated super IDs"
    )


class SingleSuperIDResponse(BaseModel):
    """
    Response model for a single super_id.
    """

    super_id: UUID


class BatchSuperIDResponse(BaseModel):
    """
    Response model for a batch of super_ids.
    """

    super_ids: List[UUID]


class MessageResponse(BaseModel):
    """
    Generic message response, typically used for errors.
    """

    detail: str
