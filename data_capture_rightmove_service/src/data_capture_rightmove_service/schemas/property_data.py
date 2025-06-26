"""
Schemas for property data requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# Base schemas for shared fields
class PropertyBase(BaseModel):
    """Base schema for property data requests."""
    
    property_id: int = Field(..., description="Rightmove property ID")
    description: Optional[str] = Field(None, description="Optional description for tracking purposes")


# Request schemas
class FetchPropertyDetailsRequest(BaseModel):
    """Request to fetch property details from Rightmove."""
    
    property_id: Optional[int] = Field(
        None, 
        description="Rightmove property ID"
    )
    property_url: Optional[str] = Field(
        None, 
        description="Rightmove property URL (alternative to property_id)"
    )
    super_id: Optional[UUID] = Field(
        None,
        description="Optional Super ID for tracking purposes"
    )
    description: Optional[str] = Field(
        None, 
        description="Optional description for tracking purposes"
    )
    
    @model_validator(mode='after')
    def validate_property_identifier(self):
        # This validator runs after the model is created and all fields are set
        # Check that at least one of property_id or property_url is provided
        if not self.property_id and not self.property_url:
            raise ValueError("Either property_id or property_url must be provided")
        return self
        
    class Config:
        schema_extra = {
            "example": {
                "property_id": 123456789,
                "description": "Property listing for review"
            }
        }


class FetchBatchRequest(BaseModel):
    """Request to fetch a batch of properties."""
    
    property_ids: List[int] = Field(..., description="List of Rightmove property IDs to fetch")
    api_type: str = Field(..., description="API type to use: 'properties_details' or 'property_for_sale'")


# Response schemas
class FetchPropertyResponse(BaseModel):
    """Response for a property fetch operation."""
    
    property_id: int = Field(..., description="Rightmove property ID")
    super_id: UUID = Field(..., description="Tracking UUID")
    status: str = Field(..., description="Status of the fetch operation")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of operation")
    message: Optional[str] = Field(None, description="Additional information")


class FetchBatchResponse(BaseModel):
    """Response for a batch fetch operation."""
    
    batch_id: UUID = Field(..., description="Batch operation ID")
    total: int = Field(..., description="Total number of properties in batch")
    successful: int = Field(..., description="Number of successfully fetched properties")
    failed: int = Field(..., description="Number of failed fetch operations")
    results: List[FetchPropertyResponse] = Field(..., description="Individual property fetch results")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of operation")


# Data storage schemas
class PropertyDetailsStorageResponse(BaseModel):
    """Response when property details have been stored."""
    
    property_id: int = Field(..., description="Rightmove property ID")
    super_id: UUID = Field(..., description="Tracking UUID")
    stored: bool = Field(..., description="Whether the property was stored successfully")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of storage")
    message: Optional[str] = Field(None, description="Additional information about storage")
    
    class Config:
        schema_extra = {
            "example": {
                "property_id": 12345678,
                "super_id": "123e4567-e89b-12d3-a456-426614174000",
                "stored": True,
                "timestamp": "2023-10-25T12:34:56.789Z",
                "message": "Property data stored successfully"
            }
        }


# Search request schemas
class PropertySearchRequest(BaseModel):
    """Request to search for properties based on criteria."""
    
    location: str = Field(..., description="Location identifier or name")
    min_price: Optional[int] = Field(None, description="Minimum price")
    max_price: Optional[int] = Field(None, description="Maximum price")
    min_bedrooms: Optional[int] = Field(None, description="Minimum number of bedrooms")
    max_bedrooms: Optional[int] = Field(None, description="Maximum number of bedrooms")
    property_type: Optional[str] = Field(None, description="Type of property")
    radius: Optional[float] = Field(None, description="Search radius in miles")
    page_number: int = Field(0, description="Page number for pagination")
    page_size: int = Field(10, description="Number of results per page")
    
    class Config:
        schema_extra = {
            "example": {
                "location": "London",
                "min_price": 200000,
                "max_price": 500000,
                "min_bedrooms": 2,
                "max_bedrooms": 3,
                "property_type": "FLAT",
                "radius": 1.0,
                "page_number": 0,
                "page_size": 10
            }
        }
