from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID # Added for client_id type hint, though it will be str in response

from pydantic import BaseModel, Field, ConfigDict


class AppClientTokenData(BaseModel):
    client_id: str = Field(..., alias="sub")
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    exp: int
    iss: Optional[str] = None
    aud: Optional[str] = None


class AppClientCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=3, max_length=100, description="Name of the application client.")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the client.")
    allowed_callback_urls: List[str] = Field(
        ...,
        description="List of allowed callback URLs for OAuth2/OIDC flows.",
        examples=[["https://myapp.com/callback", "http://localhost:8080/oauth/callback"]]
    )
    assigned_roles: Optional[List[str]] = Field(
        default_factory=list,
        description="Optional list of role names to assign to this app client.",
        examples=[["reader", "writer"]]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "client_name": "My Frontend App",
                    "description": "Main frontend application for user interaction.",
                    "allowed_callback_urls": ["https://myapp.com/callback", "http://localhost:3000/auth/callback"],
                    "assigned_roles": ["user_basic_access"]
                }
            ]
        }
    )


class AppClientCreatedResponse(BaseModel):
    client_id: str = Field(..., description="The unique identifier for the app client (UUID).")
    client_secret: str = Field(..., description="The client secret. This is only shown once upon creation.")
    client_name: str = Field(..., description="Name of the application client.")
    description: Optional[str] = Field(None, description="Optional description for the client.")
    allowed_callback_urls: List[str] = Field(..., description="List of allowed callback URLs.")
    assigned_roles: List[str] = Field(default_factory=list, description="List of role names assigned to this app client.")
    is_active: bool = Field(default=True, description="Whether the client is active.")
    created_at: datetime = Field(..., description="Timestamp of when the client was created.")
    updated_at: datetime = Field(..., description="Timestamp of when the client was last updated.")

    model_config = ConfigDict(from_attributes=True)


class AppClientResponse(BaseModel):
    client_id: str = Field(..., description="The unique identifier for the app client (UUID).")
    client_name: str = Field(..., description="Name of the application client.")
    description: Optional[str] = Field(None, description="Optional description for the client.")
    allowed_callback_urls: List[str] = Field(..., description="List of allowed callback URLs.")
    assigned_roles: List[str] = Field(default_factory=list, description="List of role names assigned to this app client.")
    is_active: bool = Field(default=True, description="Whether the client is active.")
    created_at: datetime = Field(..., description="Timestamp of when the client was created.")
    updated_at: datetime = Field(..., description="Timestamp of when the client was last updated.")

    model_config = ConfigDict(from_attributes=True)


class AppClientListResponse(BaseModel):
    clients: List[AppClientResponse] = Field(..., description="List of app clients.")
    count: int = Field(..., description="Total count of clients.")


class AppClientUpdateRequest(BaseModel):
    client_name: Optional[str] = Field(None, min_length=3, max_length=100, description="Name of the application client.")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the client.")
    allowed_callback_urls: Optional[List[str]] = Field(
        None,
        description="List of allowed callback URLs for OAuth2/OIDC flows.",
    )
    is_active: Optional[bool] = Field(None, description="Whether the client is active.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "client_name": "Updated App Name",
                    "description": "Updated description",
                    "allowed_callback_urls": ["https://updated-app.com/callback"],
                    "is_active": True
                }
            ]
        }
    )


class AppClientTokenRequest(BaseModel):
    grant_type: Literal["client_credentials"] = Field(..., description="OAuth2 grant type, must be 'client_credentials'.")
    client_id: str = Field(..., description="The client ID.")
    client_secret: str = Field(..., description="The client secret.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grant_type": "client_credentials",
                    "client_id": "550e8400-e29b-41d4-a716-446655440000",
                    "client_secret": "a-very-secret-key-generated-by-the-system"
                }
            ]
        }
    )


class AccessTokenResponse(BaseModel):
    access_token: str = Field(..., description="The JWT access token.")
    token_type: Literal["Bearer"] = Field(default="Bearer", description="The type of token, always 'Bearer'.")
    expires_in: int = Field(..., description="Token expiration time in seconds.")

