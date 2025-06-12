from typing import List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class UserRoleAssign(BaseModel):
    """Schema for assigning a role to a user"""
    role_id: uuid.UUID = Field(..., description="ID of the role to assign to the user")


class UserRoleResponse(BaseModel):
    """Schema for a user-role assignment response"""
    user_id: uuid.UUID = Field(..., description="ID of the user")
    role_id: uuid.UUID = Field(..., description="ID of the role")
    assigned_at: datetime = Field(..., description="Timestamp when the role was assigned to the user")


class UserRoleListResponse(BaseModel):
    """Schema for a list of user-role assignments"""
    items: List[UserRoleResponse] = Field(default_factory=list, description="List of user-role assignments")
    count: int = Field(..., description="Total number of user-role assignments")
