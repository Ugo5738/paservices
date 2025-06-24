import os
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # General App settings
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT, alias="AUTH_SERVICE_ENVIRONMENT"
    )
    LOGGING_LEVEL: str = Field("INFO", alias="AUTH_SERVICE_LOGGING_LEVEL")
    ROOT_PATH: str = Field("/api/v1", alias="AUTH_SERVICE_ROOT_PATH")

    # Database Configuration
    DATABASE_URL: str = Field(..., alias="AUTH_SERVICE_DATABASE_URL")

    # Supabase Configuration
    SUPABASE_URL: str = Field(..., alias="AUTH_SERVICE_SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(..., alias="AUTH_SERVICE_SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ..., alias="AUTH_SERVICE_SUPABASE_SERVICE_ROLE_KEY"
    )
    SUPABASE_EMAIL_CONFIRMATION_REQUIRED: bool = Field(
        True, alias="AUTH_SERVICE_SUPABASE_EMAIL_CONFIRMATION_REQUIRED"
    )
    SUPABASE_AUTO_CONFIRM_NEW_USERS: bool = Field(
        False, alias="AUTH_SERVICE_SUPABASE_AUTO_CONFIRM_NEW_USERS"
    )

    # M2M JWT Configuration
    M2M_JWT_SECRET_KEY: str = Field(..., alias="AUTH_SERVICE_M2M_JWT_SECRET_KEY")
    M2M_JWT_ALGORITHM: str = Field("HS256", alias="AUTH_SERVICE_M2M_JWT_ALGORITHM")
    M2M_JWT_ISSUER: str = Field(
        "paservices_auth_service", alias="AUTH_SERVICE_M2M_JWT_ISSUER"
    )
    M2M_JWT_AUDIENCE: str = Field(
        "paservices_microservices", alias="AUTH_SERVICE_M2M_JWT_AUDIENCE"
    )
    M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        30, alias="AUTH_SERVICE_M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Self-hosted Supabase configuration
    SUPABASE_SELF_HOSTED: bool = False
    SUPABASE_DB_HOST: str | None = None
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_USER: str = "postgres"
    SUPABASE_DB_PASSWORD: str | None = None

    # Rate Limiting & Redis
    REDIS_URL: str = Field("redis://localhost:6379/0", alias="AUTH_SERVICE_REDIS_URL")

    # Bootstrap and Redirect Settings
    INITIAL_ADMIN_EMAIL: str = Field(
        "admin@admin.com", alias="AUTH_SERVICE_INITIAL_ADMIN_EMAIL"
    )
    INITIAL_ADMIN_PASSWORD: str = Field(
        "admin", alias="AUTH_SERVICE_INITIAL_ADMIN_PASSWORD"
    )
    EMAIL_CONFIRMATION_REDIRECT_URL: Optional[str] = Field(
        None, alias="AUTH_SERVICE_EMAIL_CONFIRMATION_REDIRECT_URL"
    )
    PASSWORD_RESET_REDIRECT_URL: str = Field(
        "http://localhost:3000/auth/update-password",
        alias="AUTH_SERVICE_PASSWORD_RESET_REDIRECT_URL",
    )

    # Rate Limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_TOKEN: str = "10/minute"
    RATE_LIMIT_PASSWORD_RESET: str = "3/minute"
    RATE_LIMIT_REQUESTS_PER_MINUTE: Optional[str] = None
    RATE_LIMIT_WINDOW_SECONDS: Optional[str] = None

    # JWT Refresh Token Settings
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = Field(
        60 * 24 * 7, alias="JWT_REFRESH_TOKEN_EXPIRE_MINUTES"
    )  # 7 days

    # OAuth Settings
    OAUTH_REDIRECT_URI: str = Field(
        "http://localhost:8000/auth/users/login/google/callback",
        alias="OAUTH_REDIRECT_URI",
    )
    OAUTH_STATE_COOKIE_NAME: str = Field("auth_state", alias="OAUTH_STATE_COOKIE_NAME")
    OAUTH_STATE_COOKIE_MAX_AGE_SECONDS: int = Field(
        300, alias="OAUTH_STATE_COOKIE_MAX_AGE_SECONDS"
    )  # 5 minutes
    OAUTH_CALLBACK_ROUTE_BASE: Optional[str] = None

    # Provider-specific OAuth Settings
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(None, alias="GOOGLE_CLIENT_SECRET")

    # AWS Credentials (generally not recommended here, but supported if needed)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None

    @field_validator("DATABASE_URL")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # If we're using self-hosted Supabase, ensure the database URL is configured correctly
        self_hosted = info.data.get("SUPABASE_SELF_HOSTED", False)
        if (
            self_hosted
            and not v
            and all(
                [
                    info.data.get("SUPABASE_DB_HOST"),
                    info.data.get("SUPABASE_DB_PASSWORD"),
                ]
            )
        ):
            # Construct DB URL from self-hosted Supabase components
            db_host = info.data.get("SUPABASE_DB_HOST")
            db_port = info.data.get("SUPABASE_DB_PORT", 5432)
            db_name = info.data.get("SUPABASE_DB_NAME", "postgres")
            db_user = info.data.get("SUPABASE_DB_USER", "postgres")
            db_pass = info.data.get("SUPABASE_DB_PASSWORD")
            return f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        return v

    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        return self.ENVIRONMENT == Environment.TESTING

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Instantiate the settings
settings = Settings()
