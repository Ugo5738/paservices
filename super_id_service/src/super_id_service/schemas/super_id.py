"""
Schema models for the Super ID Service.

This module contains Pydantic models for request/response validation 
and serialization/deserialization.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SuperIDRequest(BaseModel):
    """Request schema for generating one or more super IDs."""
    count: int = Field(default=1, ge=1, le=100, description="Number of super IDs to generate")
    metadata: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional metadata to associate with the generated super IDs"
    )


class SingleSuperIDResponse(BaseModel):
    """Response schema for a single super ID."""
    super_id: UUID = Field(..., description="The generated super ID (UUID v4)")
    
    model_config = ConfigDict(from_attributes=True)


class BatchSuperIDResponse(BaseModel):
    """Response schema for a batch of super IDs."""
    super_ids: List[UUID] = Field(..., description="List of generated super IDs (UUID v4)")
    
    model_config = ConfigDict(from_attributes=True)


class SuperIDDetails(BaseModel):
    """Detailed schema for a super ID record with metadata."""
    super_id: UUID = Field(..., description="The generated super ID (UUID v4)")
    generated_at: datetime = Field(..., description="Timestamp when the ID was generated")
    requested_by_client_id: Optional[str] = Field(None, description="The client ID that requested the super ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata associated with this super ID")
    
    model_config = ConfigDict(from_attributes=True)
