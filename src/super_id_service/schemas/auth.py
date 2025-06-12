"""
Authentication schemas for Super ID Service.

This module contains Pydantic models for JWT token validation and auth data.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class TokenData(BaseModel):
    """Schema representing validated JWT token data."""
    
    sub: str = Field(..., description="Subject claim from JWT (usually client_id)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    permissions: List[str] = Field(default_factory=list, description="Permissions granted to the client")
    iss: Optional[str] = Field(None, description="Issuer of the token")
    client_id: Optional[str] = Field(None, description="Client ID if specified separately")
    
    model_config = ConfigDict(from_attributes=True)
