# super_id_service/src/super_id_service/config.py
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
    PROJECT_NAME: str = Field(
        "Super ID Service",
        alias="SUPER_ID_SERVICE_PROJECT_NAME",
        description="Project name",
    )
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT,
        alias="SUPER_ID_SERVICE_ENVIRONMENT",
        description="Application environment",
    )
    ROOT_PATH: str = Field(
        "/api/v1",
        alias="SUPER_ID_SERVICE_ROOT_PATH",
        description="API root path for reverse proxies",
    )
    LOGGING_LEVEL: str = Field(
        "INFO",
        alias="SUPER_ID_SERVICE_LOGGING_LEVEL",
        description="Logging level",
    )

    # Database configuration
    database_url: str = Field(...)
    use_pgbouncer: bool = False

    # Supabase configuration with standardized service-specific prefixes
    supabase_url: str = Field(..., validation_alias="SUPER_ID_SERVICE_SUPABASE_URL")
    supabase_anon_key: str = Field(
        ..., validation_alias="SUPER_ID_SERVICE_SUPABASE_ANON_KEY"
    )
    supabase_service_role_key: str = Field(
        ..., validation_alias="SUPER_ID_SERVICE_SUPABASE_SERVICE_ROLE_KEY"
    )

    # JWT configuration (for validating auth_service JWTs)
    # Use validation_alias to specify the exact environment variable name
    JWT_SECRET_KEY: str = Field(
        ..., validation_alias="SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY"
    )
    AUTH_SERVICE_ISSUER: str = Field(
        "paservices_auth_service",
        validation_alias="SUPER_ID_SERVICE_AUTH_SERVICE_ISSUER",
    )
    AUTH_SERVICE_AUDIENCE: str = Field(
        "paservices_microservices",
        validation_alias="SUPER_ID_SERVICE_AUTH_SERVICE_AUDIENCE",
    )

    AUTH_SERVICE_URL: str = Field(
        "https://auth.supersami.com/api/v1/auth",
        alias="SUPER_ID_SERVICE_AUTH_SERVICE_URL",
        description="Auth Service URL for token acquisition",
    )
    AUTH_SERVICE_JWT_ALGORITHM: str = Field(
        "RS256",
        validation_alias="SUPER_ID_SERVICE_AUTH_SERVICE_JWT_ALGORITHM",
    )
    SUPER_ID_SERVICE_RESOURCE_URL: str = Field(
        "https://super-id.supersami.com/api/v1/super_id_service",
        alias="SUPER_ID_SERVICE_RESOURCE_URL",
        description="Super ID Resource URL for MCP",
    )
    SUPER_ID_SERVICE_DOCUMENTATION_URL: str = Field(
        "https://super-id.supersami.com/docs",
        alias="SUPER_ID_SERVICE_DOCUMENTATION_URL",
        description="Super ID Documentation URL",
    )
    SUPER_ID_SERVICE_RESOURCE_METADATA_URL: str = Field(
        "https://super-id.supersami.com/api/v1/super_id_service/.well-known/oauth-protected-resource",
        alias="SUPER_ID_SERVICE_RESOURCE_METADATA_URL",
        description="Super ID Resource Metadata URL",
    )

    # Rate limiting
    rate_limit_requests_per_minute: str = "60/minute"

    # Redis configuration (optional, for rate limiting)
    redis_url: Optional[str] = None

    # CORS settings
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    # # MCP settings
    # MCP_PROJECT_ID: str = Field(
    #     ..., validation_alias="SUPER_ID_SERVICE_STYTCH_PROJECT_ID"
    # )
    # MCP_DOMAIN: str = Field(..., validation_alias="SUPER_ID_SERVICE_STYTCH_DOMAIN")
    # MCP_SECRET_KEY: str = Field(..., validation_alias="SUPER_ID_SERVICE_STYTCH_SECRET")
    # MCP_CLIENT_ID: str = Field(
    #     ..., validation_alias="SUPER_ID_SERVICE_STYTCH_CLIENT_ID"
    # )
    # MCP_CLIENT_SECRET: str = Field(
    #     ..., validation_alias="SUPER_ID_SERVICE_STYTCH_CLIENT_SECRET"
    # )

    @field_validator("database_url")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # Return the database URL as is, add validation if needed
        return v

    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        return self.ENVIRONMENT == Environment.TESTING

    model_config = SettingsConfigDict(
        env_prefix="SUPER_ID_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Create a global instance of the settings
settings = Settings()
