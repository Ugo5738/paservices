from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class RolePermissionAssign(BaseModel):
    """Schema for assigning a permission to a role"""
    permission_id: UUID = Field(..., description="The ID of the permission to assign to the role")


class RolePermissionRemove(BaseModel):
    """Schema for removing a permission from a role"""
    permission_id: UUID = Field(..., description="The ID of the permission to remove from the role")


class RolePermissionResponse(BaseModel):
    """Schema for role-permission relationship response"""
    role_id: UUID
    permission_id: UUID
    assigned_at: datetime

    class Config:
        from_attributes = True


class RolePermissionListResponse(BaseModel):
    """Schema for list of role-permission relationships"""
    items: List[RolePermissionResponse]
    count: int = Field(..., description="Total number of role-permission relationships")
