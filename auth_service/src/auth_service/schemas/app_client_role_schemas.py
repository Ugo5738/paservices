from typing import List
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class AppClientRoleAssign(BaseModel):
    """Schema for assigning a role to an app client"""
    role_id: uuid.UUID = Field(..., description="ID of the role to assign to the app client")


class AppClientRoleResponse(BaseModel):
    """Schema for an app-client-role assignment response"""
    app_client_id: uuid.UUID = Field(..., description="ID of the app client")
    role_id: uuid.UUID = Field(..., description="ID of the role")
    assigned_at: datetime = Field(..., description="Timestamp when the role was assigned to the app client")


class AppClientRoleListResponse(BaseModel):
    """Schema for a list of app-client-role assignments"""
    items: List[AppClientRoleResponse] = Field(default_factory=list, description="List of app-client-role assignments")
    count: int = Field(..., description="Total number of app-client-role assignments")
