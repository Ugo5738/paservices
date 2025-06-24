from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PermissionCreate(BaseModel):
    """Schema for creating a new permission"""

    name: str = Field(
        ..., description="Unique name for the permission (e.g., 'users:read')"
    )
    description: Optional[str] = Field(
        None, description="Optional description of the permission"
    )


class PermissionUpdate(BaseModel):
    """Schema for updating an existing permission"""

    name: Optional[str] = Field(None, description="New name for the permission")
    description: Optional[str] = Field(
        None, description="New description for the permission"
    )


class PermissionResponse(BaseModel):
    """Schema for permission response"""

    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionListResponse(BaseModel):
    """Schema for list of permissions response"""

    items: List[PermissionResponse]
    count: int = Field(..., description="Total number of permissions")
