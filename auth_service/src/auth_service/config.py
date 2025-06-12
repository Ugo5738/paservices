import os
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    supabase_url: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_URL"}
    )
    supabase_anon_key: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_ANON_KEY"}
    )
    supabase_service_role_key: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_SERVICE_ROLE_KEY"}
    )
    supabase_email_confirmation_required: bool = Field(
        default=True,
        json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_EMAIL_CONFIRMATION_REQUIRED"},
    )
    supabase_auto_confirm_new_users: bool = Field(
        default=False,
        json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_AUTO_CONFIRM_NEW_USERS"},
    )

    # Self-hosted Supabase configuration
    supabase_self_hosted: bool = Field(
        default=False, json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_SELF_HOSTED"}
    )
    supabase_db_host: str | None = Field(
        default=None, json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_DB_HOST"}
    )
    supabase_db_port: int = Field(
        default=5432, json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_DB_PORT"}
    )
    supabase_db_name: str = Field(
        default="postgres", json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_DB_NAME"}
    )
    supabase_db_user: str = Field(
        default="postgres", json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_DB_USER"}
    )
    supabase_db_password: str | None = Field(
        default=None, json_schema_extra={"env": "AUTH_SERVICE_SUPABASE_DB_PASSWORD"}
    )
    m2m_jwt_secret_key: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_M2M_JWT_SECRET_KEY"}
    )
    m2m_jwt_algorithm: str = Field(
        default="HS256", json_schema_extra={"env": "M2M_JWT_ALGORITHM"}
    )
    m2m_jwt_issuer: str = Field(
        default="paservices_auth_service", json_schema_extra={"env": "M2M_JWT_ISSUER"}
    )
    m2m_jwt_audience: str = Field(
        default="paservices_microservices",
        json_schema_extra={"env": "M2M_JWT_AUDIENCE"},
    )
    m2m_jwt_access_token_expire_minutes: int = Field(
        default=30, json_schema_extra={"env": "M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES"}
    )
    auth_service_database_url: str = Field(
        ..., json_schema_extra={"env": "AUTH_SERVICE_DATABASE_URL"}
    )
    use_pgbouncer: bool = Field(
        default=False, json_schema_extra={"env": "USE_PGBOUNCER"}
    )
    root_path: str = Field("", json_schema_extra={"env": "ROOT_PATH"})

    # Define the fields from your .env file
    rate_limit_login: str = Field(
        default="5/minute", json_schema_extra={"env": "RATE_LIMIT_LOGIN"}
    )
    rate_limit_register: str = Field(
        default="5/minute", json_schema_extra={"env": "RATE_LIMIT_REGISTER"}
    )
    rate_limit_token: str = Field(
        default="10/minute", json_schema_extra={"env": "RATE_LIMIT_TOKEN"}
    )
    rate_limit_password_reset: str = Field(
        default="3/minute", json_schema_extra={"env": "RATE_LIMIT_PASSWORD_RESET"}
    )

    initial_admin_email: str = Field(
        default="admin@admin.com", json_schema_extra={"env": "INITIAL_ADMIN_EMAIL"}
    )
    initial_admin_password: str = Field(
        default="admin", json_schema_extra={"env": "INITIAL_ADMIN_PASSWORD"}
    )

    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # OAuth Settings
    OAUTH_REDIRECT_URI: str = (
        "http://localhost:8000/auth/users/login/google/callback"  # Default, adjust per provider if needed
    )
    OAUTH_STATE_COOKIE_NAME: str = "pa_oauth_state"
    OAUTH_STATE_COOKIE_MAX_AGE_SECONDS: int = 300  # 5 minutes

    # Provider-specific OAuth Settings (Example for Google, extend as needed)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    logging_level: str = Field(
        default="INFO", json_schema_extra={"env": "LOGGING_LEVEL"}
    )
    PASSWORD_RESET_REDIRECT_URL: str = Field(
        default="http://localhost:3000/auth/update-password",
        json_schema_extra={"env": "PASSWORD_RESET_REDIRECT_URL"},
    )

    # Environment configuration
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, json_schema_extra={"env": "ENVIRONMENT"}
    )

    base_url: Optional[str] = Field(None, json_schema_extra={"env": "BASE_URL"})
    redis_url: Optional[str] = Field(None, json_schema_extra={"env": "REDIS_URL"})
    oauth_callback_route_base: Optional[str] = Field(
        None, json_schema_extra={"env": "OAUTH_CALLBACK_ROUTE_BASE"}
    )
    email_confirmation_redirect_url: Optional[str] = Field(
        None, json_schema_extra={"env": "EMAIL_CONFIRMATION_REDIRECT_URL"}
    )

    # AWS Credentials (consider if these should truly be in app settings vs. handled by instance roles/env vars for deployment)
    aws_access_key_id: Optional[str] = Field(
        None, json_schema_extra={"env": "AWS_ACCESS_KEY_ID"}
    )
    aws_secret_access_key: Optional[str] = Field(
        None, json_schema_extra={"env": "AWS_SECRET_ACCESS_KEY"}
    )

    rate_limit_requests_per_minute: Optional[str] = Field(
        None, json_schema_extra={"env": "RATE_LIMIT_REQUESTS_PER_MINUTE"}
    )
    rate_limit_window_seconds: Optional[str] = Field(
        None, json_schema_extra={"env": "RATE_LIMIT_WINDOW_SECONDS"}
    )

    @field_validator("auth_service_database_url")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # If we're using self-hosted Supabase, ensure the database URL is configured correctly
        # This allows the auth service to connect to the same database as Supabase
        self_hosted = getattr(info.data, "supabase_self_hosted", False)
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

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Settings()
