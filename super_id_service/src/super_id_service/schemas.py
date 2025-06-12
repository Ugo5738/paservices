"""
Pydantic models (schemas) for the Super ID Service.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class SuperIdRequest(BaseModel):
    """
    Request model for generating super_ids.
    """
    count: int = Field(default=1, ge=1, le=100, description="Number of IDs to generate")


class SuperIdResponse(BaseModel):
    """
    Response model for a single super_id.
    """
    super_id: UUID = Field(description="Generated UUID v4")


class SuperIdListResponse(BaseModel):
    """
    Response model for multiple super_ids.
    """
    super_ids: List[UUID] = Field(description="List of generated UUID v4s")


class MessageResponse(BaseModel):
    """
    Generic message response, typically used for errors.
    """
    detail: str = Field(description="Response message")


class TokenData(BaseModel):
    """
    Data extracted from a validated JWT.
    """
    sub: str = Field(description="Subject (usually client_id)")
    permissions: List[str] = Field(default_factory=list, description="Permissions from JWT")
    iss: Optional[str] = Field(None, description="Issuer")
    exp: Optional[int] = Field(None, description="Expiration time")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata from JWT")
