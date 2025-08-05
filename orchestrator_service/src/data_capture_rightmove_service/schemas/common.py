"""
Common schemas shared across multiple endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Standard message response for API operations."""
    
    message: str = Field(..., description="Response message")
    success: bool = Field(..., description="Operation success status")


class ErrorResponse(BaseModel):
    """Standard error response for API operations."""
    
    detail: str = Field(..., description="Error detail")
    error_type: Optional[str] = Field(None, description="Type of error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of error")


class HealthStatus(str, Enum):
    """Health status enum for health check responses."""
    
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    DEGRADED = "degraded"


class ComponentHealth(BaseModel):
    """Health information for a single component."""
    
    status: HealthStatus = Field(..., description="Status of the component")
    message: Optional[str] = Field(None, description="Optional message about the component health")


class HealthCheckResponse(BaseModel):
    """Standard health check response."""
    
    status: HealthStatus = Field(..., description="Overall service health status")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of health check")
    components: Dict[str, ComponentHealth] = Field(..., description="Health of individual components")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime in seconds")
