"""
Pydantic models for authentication data, such as JWT claims.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenData(BaseModel):
    """
    Data extracted from a validated JWT.
    """

    sub: str = Field(..., description="Subject (usually client_id)")
    permissions: List[str] = Field(
        default_factory=list, description="Permissions from JWT"
    )
    iss: Optional[str] = Field(None, description="Issuer of the token")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    # Using alias to match the field name in the dependency
    client_id: Optional[str] = Field(None, alias="sub")
