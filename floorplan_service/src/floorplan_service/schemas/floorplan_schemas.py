# src/floorplan_service/schemas/floorplan_schemas.py

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# --- Request Schemas ---


class FloorplanInput(BaseModel):
    """Client-provided information for a single floorplan image."""

    url: HttpUrl
    notes: Optional[str] = None


class FloorplanAnalysisRequest(BaseModel):
    """Payload to initiate the floorplan analysis process."""

    super_id: uuid.UUID
    property_id: str
    floorplans: Dict[str, FloorplanInput]


# --- Webhook Schemas (Matching incoming data from the analyzer) ---


class AllFloorsInfo(BaseModel):
    """Nested object within the webhook payload containing URLs."""

    json_file_url: Optional[HttpUrl] = None
    csv_url: Optional[HttpUrl] = None
    total_area_csv_url: Optional[HttpUrl] = None
    image_labelme_side_by_side_url: Optional[HttpUrl] = None
    notes: Optional[str] = None


class WebhookOutputData(BaseModel):
    """Represents a single processed floorplan item in the webhook's output_data list."""

    property_id: str
    floorplan_id: str  # This will be the key provided by the client (e.g., "fp1")
    original_url: HttpUrl
    all_floors: AllFloorsInfo


class WebhookPayload(BaseModel):
    """The root object of the incoming webhook request."""

    task: str
    message: Optional[str] = None
    # user_id: str # The analyzer service might still send this; we can log it but won't store it.
    property_id: str
    output_data: List[WebhookOutputData]


# --- Response Schemas (For GET endpoints, mapping from new DB models) ---


class FpRoomCsvDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    floor_name: Optional[str] = None
    room_name: Optional[str] = None
    dimensions_imperial: Optional[str] = None
    dimensions_metric: Optional[str] = None
    room_id: Optional[float] = None
    calculated_sq_area_metric_csv: Optional[float] = None
    calculated_area_imperial_csv: Optional[float] = None


class FpTotalAreasCsvDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    area_name: Optional[str] = None
    square_meters: Optional[float] = None
    square_feet: Optional[float] = None
    total_floors: Optional[int] = None
    total_named_rooms: Optional[int] = None


class FpAnalysisUrlsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    json_file_url: Optional[HttpUrl] = None
    csv_url: Optional[HttpUrl] = None
    total_area_csv_url: Optional[HttpUrl] = None
    notes: Optional[str] = None
    all_floors_csv_data: List[FpRoomCsvDataResponse] = []
    total_areas_csv_data: List[FpTotalAreasCsvDataResponse] = []


class PropertyDetailResponse(BaseModel):
    """Detailed response for a single property, including all nested data."""

    model_config = ConfigDict(from_attributes=True)

    message: str
    property_id: str
    super_id: str
    floorplan_id: str
    original_url: HttpUrl
    created_at: datetime
    updated_at: datetime
    analysis_urls: Optional[FpAnalysisUrlsResponse] = None


class PropertyOverviewResponse(BaseModel):
    """Simplified response for listing multiple properties."""

    model_config = ConfigDict(from_attributes=True)

    property_id: str
    floorplan_id: str
    super_id: uuid.UUID
    message: str
    original_url: HttpUrl
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
