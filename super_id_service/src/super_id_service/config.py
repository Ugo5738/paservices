"""
Configuration module for loading environment variables using pydantic-settings.
"""

import os
from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Settings for the Super ID Service.
    Loads environment variables, with fallbacks to default values where appropriate.
    """

    # Core settings
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        json_schema_extra={"env": "SUPER_ID_SERVICE_ENVIRONMENT"},
    )
    root_path: str = Field("", json_schema_extra={"env": "SUPER_ID_SERVICE_ROOT_PATH"})
    log_level: str = Field(
        "INFO", json_schema_extra={"env": "SUPER_ID_SERVICE_LOGGING_LEVEL"}
    )

    # Database configuration
    super_id_service_database_url: str = Field(
        ..., json_schema_extra={"env": "SUPER_ID_SERVICE_DATABASE_URL"}
    )
    use_pgbouncer: bool = Field(
        default=False, json_schema_extra={"env": "SUPER_ID_SERVICE_USE_PGBOUNCER"}
    )

    # Supabase configuration
    supabase_url: str = Field(
        ..., json_schema_extra={"env": "SUPER_ID_SERVICE_SUPABASE_URL"}
    )
    supabase_anon_key: str = Field(
        ..., json_schema_extra={"env": "SUPER_ID_SERVICE_SUPABASE_ANON_KEY"}
    )
    supabase_service_role_key: str = Field(
        ..., json_schema_extra={"env": "SUPER_ID_SERVICE_SUPABASE_SERVICE_ROLE_KEY"}
    )

    # JWT configuration (for validating auth_service JWTs)
    jwt_secret_key: str = Field(
        ..., json_schema_extra={"env": "SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY"}
    )
    auth_service_issuer: str = Field(
        "auth.supersami.com",
        json_schema_extra={"env": "SUPER_ID_SERVICE_AUTH_SERVICE_ISSUER"},
    )

    # Rate limiting
    rate_limit_requests_per_minute: str = Field(
        default="60/minute",
        json_schema_extra={"env": "SUPER_ID_SERVICE_RATE_LIMIT_REQUESTS_PER_MINUTE"},
    )

    # Redis configuration (optional, for rate limiting)
    redis_url: Optional[str] = Field(
        None, json_schema_extra={"env": "SUPER_ID_SERVICE_REDIS_URL"}
    )

    # CORS settings
    cors_allow_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        json_schema_extra={"env": "SUPER_ID_SERVICE_CORS_ALLOW_ORIGINS"},
    )

    @field_validator("super_id_service_database_url")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # Return the database URL as is, add validation if needed
        return v

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING

    # Model configuration
    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


# Create a global instance of the settings
settings = Settings()
