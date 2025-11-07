"""Schemas for workflow status read/write APIs."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkflowStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    super_id: UUID
    property_id: Optional[str] = None
    context: str
    status: str
    stage: Optional[str] = None
    progress: Optional[float] = None
    data_location: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WorkflowStatusUpsertRequest(BaseModel):
    super_id: UUID
    context: str
    status: str
    property_id: Optional[str] = None
    stage: Optional[str] = None
    progress: Optional[float] = None
    data_location: Optional[str] = None
    last_error: Optional[str] = None
