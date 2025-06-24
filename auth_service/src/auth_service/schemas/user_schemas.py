from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Profile Schemas ---
class ProfileBase(BaseModel):
    email: EmailStr  # Added email field
    username: Optional[str] = Field(None, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class ProfileCreate(ProfileBase):
    user_id: UUID  # Will be populated from Supabase user ID
    # email is inherited from ProfileBase if we add it there, or can be added here if specific to creation
    # For now, assuming email is part of Supabase user and ProfileBase might not need it directly


class ProfileUpdate(BaseModel):
    # All fields are optional for an update - not inheriting from ProfileBase
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None  # Allow updating active status


class ProfileResponse(ProfileBase):
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateRequest(BaseModel):
    username: Optional[str] = Field(
        None,
        max_length=50,
        description="New username for the user.",
        examples=["new_username"],
    )
    first_name: Optional[str] = Field(
        None,
        max_length=100,
        description="New first name for the user.",
        examples=["NewFirstName"],
    )
    last_name: Optional[str] = Field(
        None,
        max_length=100,
        description="New last name for the user.",
        examples=["NewLastName"],
    )

    model_config = ConfigDict(
        extra="forbid",  # Do not allow extra fields in the request
        validate_assignment=True,  # Validate fields on assignment
        json_schema_extra={  # OpenAPI examples
            "examples": [
                {
                    "username": "johndoe_updated",
                    "first_name": "Johnathan",
                    "last_name": "Doe",
                },
                {"first_name": "Jane"},
                {"username": "new_user_name"},
            ]
        },
    )


# --- Supabase Schemas (mirroring supabase-py structure) ---
class SupabaseUser(BaseModel):
    id: UUID
    aud: str
    role: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    email_confirmed_at: Optional[datetime] = None
    phone_confirmed_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = (
        None  # Generally an alias for email_confirmed_at or phone_confirmed_at
    )
    last_sign_in_at: Optional[datetime] = None
    app_metadata: Dict[str, Any] = Field(default_factory=dict)
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    identities: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupabaseSession(
    BaseModel
):  # Renamed from SupabaseUserSession for clarity if used elsewhere
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None  # Supabase-py returns this as datetime
    refresh_token: Optional[str] = None
    user: SupabaseUser

    model_config = ConfigDict(from_attributes=True)


from enum import Enum

# --- User Authentication Schemas ---


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    # Add other providers as needed, e.g., AZURE = "azure"


class OAuthRedirectResponse(BaseModel):
    authorization_url: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class MagicLinkLoginRequest(BaseModel):
    email: EmailStr


class MagicLinkSentResponse(BaseModel):
    message: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    message: str


class EmailVerificationRequest(BaseModel):
    email: EmailStr
    

class MessageResponse(BaseModel):
    message: str


class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(
        ..., min_length=8
    )  # Enforce min_length, same as registration


class PasswordUpdateResponse(BaseModel):
    message: str


# --- User Registration Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ..., min_length=8
    )  # Ensure password meets complexity if needed
    username: Optional[str] = Field(None, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    # Any other data to be passed to Supabase sign_up options (e.g., data for user_metadata)
    # data: Optional[Dict[str, Any]] = None # If you want to pass extra data to Supabase user_metadata


class UserResponse(BaseModel):
    message: str
    session: Optional[SupabaseSession] = (
        None  # Session can be None if email confirmation is pending
    )
    profile: Optional[ProfileResponse] = (
        None  # Profile might not be created if Supabase signup fails or is pending
    )

    model_config = ConfigDict(from_attributes=True)

# Added from old models.py
class UserTokenData(BaseModel):
    user_id: str = Field(..., alias="sub")
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    exp: int
