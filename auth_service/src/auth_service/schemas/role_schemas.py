from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    """Schema for creating a new role"""

    name: str = Field(..., description="Unique name for the role")
    description: Optional[str] = Field(
        None, description="Optional description of the role"
    )


class RoleUpdate(BaseModel):
    """Schema for updating an existing role"""

    name: Optional[str] = Field(None, description="New name for the role")
    description: Optional[str] = Field(None, description="New description for the role")


class RoleResponse(BaseModel):
    """Schema for role response"""

    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    """Schema for list of roles response"""

    items: List[RoleResponse]
    count: int = Field(..., description="Total number of roles")
