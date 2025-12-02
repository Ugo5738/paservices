from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCallbackPayload(BaseModel):
    """Payload posted by n8n when a workflow finishes."""

    super_id: str = Field(..., description="Correlation ID for the workflow")
    status: str = Field(..., description="Workflow status (e.g., complete, failed, pending)")
    property_url: Optional[str] = Field(
        None, description="Property URL that was analyzed, if available"
    )
    final_result: Optional[Dict[str, Any]] = Field(
        None, description="Aggregated analysis result payload"
    )
    error: Optional[Any] = Field(None, description="Optional error information")

    model_config = ConfigDict(extra="allow")
