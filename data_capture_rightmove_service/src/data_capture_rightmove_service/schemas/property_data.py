# data_capture_rightmove_service/src/data_capture_rightmove_service/schemas/property_data.py
"""
Schemas for property data requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


# Base schemas for shared fields
class PropertyBase(BaseModel):
    """Base schema for property data requests."""

    property_id: int = Field(..., description="Rightmove property ID")
    description: Optional[str] = Field(
        None, description="Optional description for tracking purposes"
    )


# Request schemas
class FetchPropertyDetailsRequest(BaseModel):
    """Request to fetch property details from Rightmove."""

    property_id: Optional[int] = Field(None, description="Rightmove property ID")
    property_url: Optional[str] = Field(
        None, description="Rightmove property URL (alternative to property_id)"
    )
    super_id: Optional[UUID] = Field(
        None, description="Optional Super ID for tracking purposes"
    )
    description: Optional[str] = Field(
        None, description="Optional description for tracking purposes"
    )

    @model_validator(mode="after")
    def validate_property_identifier(self):
        # This validator runs after the model is created and all fields are set
        # Check that at least one of property_id or property_url is provided
        if not self.property_id and not self.property_url:
            raise ValueError("Either property_id or property_url must be provided")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "property_id": 123456789,
                "description": "Property listing for review",
            }
        }


class FetchBatchRequest(BaseModel):
    """Request to fetch a batch of properties."""

    property_ids: List[int] = Field(
        ..., description="List of Rightmove property IDs to fetch"
    )
    api_type: str = Field(
        ..., description="API type to use: 'properties_details' or 'property_for_sale'"
    )


# Response schemas
class FetchPropertyResponse(BaseModel):
    """Response for a property fetch operation."""

    property_id: int = Field(..., description="Rightmove property ID")
    super_id: UUID = Field(..., description="Tracking UUID")
    status: str = Field(..., description="Status of the fetch operation")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of operation"
    )
    message: Optional[str] = Field(None, description="Additional information")


class FetchBatchResponse(BaseModel):
    """Response for a batch fetch operation."""

    batch_id: UUID = Field(..., description="Batch operation ID")
    total: int = Field(..., description="Total number of properties in batch")
    successful: int = Field(
        ..., description="Number of successfully fetched properties"
    )
    failed: int = Field(..., description="Number of failed fetch operations")
    results: List[FetchPropertyResponse] = Field(
        ..., description="Individual property fetch results"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of operation"
    )


# Data storage schemas
class PropertyDetailsStorageResponse(BaseModel):
    """Response when property details have been stored."""

    property_id: int = Field(..., description="Rightmove property ID")
    super_id: UUID = Field(..., description="Tracking UUID")
    stored: bool = Field(
        ..., description="Whether the property was stored successfully"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of storage"
    )
    message: Optional[str] = Field(
        None, description="Additional information about storage"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "property_id": 12345678,
                "super_id": "123e4567-e89b-12d3-a456-426614174000",
                "stored": True,
                "timestamp": "2023-10-25T12:34:56.789Z",
                "message": "Property data stored successfully",
            }
        }


class PropertyUrlResponse(BaseModel):
    """Response for property URL validation and extraction"""

    url: str = Field(..., description="The URL that was checked")
    valid: bool = Field(..., description="Whether the URL is valid")
    property_id: Optional[int] = Field(
        None, description="Extracted property ID if valid"
    )
    message: str = Field(..., description="Message describing the result")


class CombinedPropertyResponseItem(BaseModel):
    """Response item for a single API call in the combined fetch endpoint"""

    api_endpoint: str = Field(..., description="The API endpoint that was called")
    property_id: int = Field(..., description="The property ID")
    super_id: UUID = Field(..., description="Super ID for tracking purposes")
    stored: bool = Field(..., description="Whether the data was stored successfully")
    message: str = Field(..., description="Success or error message")


class CombinedPropertyResponse(BaseModel):
    """Response for the combined fetch endpoint"""

    property_id: int = Field(..., description="The property ID")
    property_url: Optional[str] = Field(
        None, description="The property URL if provided"
    )
    results: List[CombinedPropertyResponseItem] = Field(
        ..., description="Results from each API call"
    )


# Search request schemas
class PropertySearchRequest(BaseModel):
    """Request to search for properties based on criteria."""

    location_identifier: str = Field(..., description="Location identifier or name")
    num_properties: Optional[int] = Field(
        None,
        description="Total number of properties to retrieve by paging through results.",
    )
    page_number: int = Field(1, description="Page number for pagination")

    # All 21 optional parameters
    sort_by: Optional[str] = Field(
        None,
        description="Sort order of the results (e.g., 'HighestPrice', 'NewestListed', 'NearestFirst').",
    )
    search_radius: Optional[float] = Field(None, description="Search radius in miles.")
    min_price: Optional[int] = Field(None, description="Minimum property price.")
    max_price: Optional[int] = Field(None, description="Maximum property price.")
    min_bedrooms: Optional[int] = Field(None, description="Minimum number of bedrooms.")
    max_bedrooms: Optional[int] = Field(None, description="Maximum number of bedrooms.")
    property_type: Optional[str] = Field(
        None, description="Comma-separated list of property types."
    )
    added_to_site: Optional[int] = Field(
        None, description="Filter by days since added to site."
    )
    keywords: Optional[str] = Field(
        None, description="Comma-separated list of keywords."
    )

    # Boolean flags
    has_garden: Optional[bool] = None
    has_new_home: Optional[bool] = None
    has_buying_schemes: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_retirement_home: Optional[bool] = None
    has_auction_property: Optional[bool] = None
    include_under_offer_sold_stc: Optional[bool] = Field(
        None, alias="has_include_under_offer_sold_stc"
    )
    do_not_show_new_home: Optional[bool] = None
    do_not_show_buying_schemes: Optional[bool] = None
    do_not_show_retirement_home: Optional[bool] = None


class PropertyListingResponse(BaseModel):
    id: int
    snapshot_id: int
    property_url: Optional[str]
    display_address: Optional[str]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    created_at: datetime
    super_id: UUID

    model_config = ConfigDict(from_attributes=True)


class FilteredPropertiesResponse(BaseModel):
    properties: List[PropertyListingResponse]


class ScrapedListingResponse(BaseModel):
    property_id: int = Field(
        ..., alias="id"
    )  # Map `id` from the model to `property_id`
    property_url: Optional[str]
    super_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FilteredScrapedPropertiesResponse(BaseModel):
    properties: List[ScrapedListingResponse]
