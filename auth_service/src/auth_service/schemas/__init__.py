from .common_schemas import MessageResponse
from .user_schemas import (
    ProfileBase,
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    UserProfileUpdateRequest,
    SupabaseUser,
    SupabaseSession,
    OAuthProvider,
    OAuthRedirectResponse,
    UserLoginRequest,
    MagicLinkLoginRequest,
    MagicLinkSentResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    PasswordUpdateRequest,
    PasswordUpdateResponse,
    UserCreate,
    UserResponse,
    UserTokenData, # Added
)
from .app_client_schemas import (
    AppClientTokenData,
    AppClientCreateRequest,  # Added
    AppClientCreatedResponse, # Added
)

__all__ = [
    "MessageResponse",
    "ProfileBase",
    "ProfileCreate",
    "ProfileUpdate",
    "ProfileResponse",
    "UserProfileUpdateRequest",
    "SupabaseUser",
    "SupabaseSession",
    "OAuthProvider",
    "OAuthRedirectResponse",
    "UserLoginRequest",
    "MagicLinkLoginRequest",
    "MagicLinkSentResponse",
    "PasswordResetRequest",
    "PasswordResetResponse",
    "PasswordUpdateRequest",
    "PasswordUpdateResponse",
    "UserCreate",
    "UserResponse",
    "UserTokenData",
    "AppClientTokenData",
    "AppClientCreateRequest",  # Added
    "AppClientCreatedResponse", # Added
]
