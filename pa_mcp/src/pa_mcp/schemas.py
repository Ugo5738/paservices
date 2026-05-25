from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCallbackPayload(BaseModel):
    """Payload posted by n8n when a workflow finishes."""

    super_id: str = Field(..., description="Correlation ID for the workflow")
    status: str = Field(..., description="Workflow status (e.g., complete, failed, pending)")
    context: Optional[str] = Field(
        None, description="Service context such as data_capture or floorplan_analysis"
    )
    property_url: Optional[str] = Field(
        None, description="Property URL that was analyzed, if available"
    )
    data_location: Optional[str] = Field(
        None, description="Optional object-store snapshot URL for large progressive payloads"
    )
    summary: Optional[Dict[str, Any]] = Field(
        None, description="Small summary payload for the latest service update"
    )
    final_result: Optional[Dict[str, Any]] = Field(
        None, description="Aggregated analysis result payload"
    )
    error: Optional[Any] = Field(None, description="Optional error information")
    error_message: Optional[str] = Field(
        None, description="Plain-text error string for workflows that do not send structured error"
    )

    model_config = ConfigDict(extra="allow")
