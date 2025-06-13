import os
from enum import Enum
from typing import Any, Literal, Optional

# Import SettingsConfigDict
from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = Field(...)
    supabase_anon_key: str = Field(...)
    supabase_service_role_key: str = Field(...)
    supabase_email_confirmation_required: bool = True
    supabase_auto_confirm_new_users: bool = False

    # Self-hosted Supabase configuration
    supabase_self_hosted: bool = False
    supabase_db_host: str | None = None
    supabase_db_port: int = 5432
    supabase_db_name: str = "postgres"
    supabase_db_user: str = "postgres"
    supabase_db_password: str | None = None

    # M2M JWT Configuration
    # Use validation_alias for the specific key name
    m2m_jwt_secret_key: str = Field(
        ..., validation_alias="AUTH_SERVICE_M2M_JWT_SECRET_KEY"
    )
    m2m_jwt_algorithm: str = "HS256"
    m2m_jwt_issuer: str = "paservices_auth_service"
    m2m_jwt_audience: str = "paservices_microservices"
    m2m_jwt_access_token_expire_minutes: int = 30

    # Database Configuration
    # Renamed field to 'database_url' for simplicity with the prefix
    database_url: str = Field(...)
    use_pgbouncer: bool = False

    # General App settings
    root_path: str = ""
    logging_level: str = "INFO"
    environment: Environment = Environment.DEVELOPMENT
    base_url: Optional[str] = None
    redis_url: Optional[str] = None
    email_confirmation_redirect_url: Optional[str] = None
    password_reset_redirect_url: str = "http://localhost:3000/auth/update-password"

    # Rate Limiting
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "5/minute"
    rate_limit_token: str = "10/minute"
    rate_limit_password_reset: str = "3/minute"
    rate_limit_requests_per_minute: Optional[str] = None
    rate_limit_window_seconds: Optional[str] = None

    # Initial Admin User
    initial_admin_email: str = "admin@admin.com"
    initial_admin_password: str = "admin"

    # JWT Refresh Token Settings
    jwt_refresh_token_expire_minutes: int = Field(
        60 * 24 * 7, alias="JWT_REFRESH_TOKEN_EXPIRE_MINUTES"
    )  # 7 days

    # OAuth Settings
    oauth_redirect_uri: str = Field(
        "http://localhost:8000/auth/users/login/google/callback",
        alias="OAUTH_REDIRECT_URI",
    )
    oauth_state_cookie_name: str = Field(
        "pa_oauth_state", alias="OAUTH_STATE_COOKIE_NAME"
    )
    oauth_state_cookie_max_age_seconds: int = Field(
        300, alias="OAUTH_STATE_COOKIE_MAX_AGE_SECONDS"
    )  # 5 minutes
    oauth_callback_route_base: Optional[str] = None

    # Provider-specific OAuth Settings
    google_client_id: Optional[str] = Field(None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(None, alias="GOOGLE_CLIENT_SECRET")

    # AWS Credentials (generally not recommended here, but supported if needed)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # NOTE: The custom validator for auth_service_database_url will no longer work with this name.
    # It has been renamed to 'database_url'
    # We will adjust the validator below.

    @field_validator("database_url")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # If we're using self-hosted Supabase, ensure the database URL is configured correctly
        self_hosted = info.data.get("supabase_self_hosted", False)
        if (
            self_hosted
            and not v
            and all(
                [
                    info.data.get("supabase_db_host"),
                    info.data.get("supabase_db_password"),
                ]
            )
        ):
            # Construct DB URL from self-hosted Supabase components
            db_host = info.data.get("supabase_db_host")
            db_port = info.data.get("supabase_db_port", 5432)
            db_name = info.data.get("supabase_db_name", "postgres")
            db_user = info.data.get("supabase_db_user", "postgres")
            db_pass = info.data.get("supabase_db_password")
            return f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        return v

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING

    model_config = SettingsConfigDict(
        env_prefix="AUTH_SERVICE_",  # <--- THE MAIN FIX
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
