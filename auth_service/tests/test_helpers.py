from unittest.mock import MagicMock
from uuid import UUID

from auth_service.config import Settings  # Added for create_default_mock_settings
from auth_service.schemas.user_schemas import (
    ProfileResponse,
    SupabaseSession,
    SupabaseUser,
    UserResponse,
)


def create_mock_supa_user(
    email: str, id_val: UUID, confirmed: bool = False, user_roles: list[str] | None = None
) -> SupabaseUser:
    now_iso = "2023-01-01T00:00:00Z"
    confirmed_at_val = now_iso if confirmed else None
    return SupabaseUser(
        id=id_val,
        aud="authenticated",
        role="authenticated",
        email=email,
        email_confirmed_at=confirmed_at_val,
        phone=None,
        confirmed_at=confirmed_at_val,  # Often alias for email_confirmed_at
        last_sign_in_at=confirmed_at_val,  # Can be None if never signed in
        app_metadata={},
        user_metadata={"roles": user_roles} if user_roles else {},
        identities=[],
        created_at=now_iso,
        updated_at=now_iso,
    )


def create_mock_supa_session(user: SupabaseUser) -> SupabaseSession:
    return SupabaseSession(
        access_token=f"mock_access_token_for_{user.id}",
        token_type="bearer",
        expires_in=3600,
        refresh_token=f"mock_refresh_token_for_{user.id}",
        user=user,
        expires_at=None,  # Or a valid datetime string/object if your model expects it
    )


def create_default_mock_settings():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.auth_service_database_url = (
        "postgresql+asyncpg://test:test@localhost:5433/test_db"
    )
    mock_settings.supabase_url = "http://mock.supabase.co"
    mock_settings.supabase_anon_key = "mock_key"
    mock_settings.jwt_secret_key = "test_secret"
    mock_settings.jwt_algorithm = "HS256"
    mock_settings.access_token_expire_minutes = 30
    mock_settings.supabase_email_confirmation_required = True
    mock_settings.supabase_auto_confirm_new_users = False
    mock_settings.initial_admin_email = "admin@example.com"
    mock_settings.initial_admin_password = "password"
    mock_settings.m2m_jwt_secret_key = "another_test_secret_key_min_32_chars"
    mock_settings.root_path = "/api/v1"
    mock_settings.rate_limit_login = "100/minute"
    # Add other rate limits if they become relevant for more tests
    # mock_settings.rate_limit_register = "5/minute"
    # mock_settings.rate_limit_token = "10/minute"
    # mock_settings.rate_limit_password_reset = "3/minute"
    return mock_settings
