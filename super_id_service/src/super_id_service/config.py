"""
Configuration module for loading environment variables using pydantic-settings.
"""

import os
from enum import Enum
from typing import Any, List, Literal, Optional

# Use validation_alias for specific overrides
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
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    root_path: str = ""
    log_level: str = "INFO"

    # Database configuration
    database_url: str = Field(...)  # Renamed for simplicity with prefix
    use_pgbouncer: bool = False

    # Supabase configuration
    supabase_url: str = Field(...)
    supabase_anon_key: str = Field(...)
    supabase_service_role_key: str = Field(...)

    # JWT configuration (for validating auth_service JWTs)
    # Use validation_alias to specify the exact environment variable name
    jwt_secret_key: str = Field(
        ..., validation_alias="SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY"
    )
    auth_service_issuer: str = "auth.supersami.com"

    # Rate limiting
    rate_limit_requests_per_minute: str = "60/minute"

    # Redis configuration (optional, for rate limiting)
    redis_url: Optional[str] = None

    # CORS settings
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    @field_validator("database_url")
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
    model_config = SettingsConfigDict(
        env_prefix="SUPER_ID_SERVICE_",  # <-- This is the main fix
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Create a global instance of the settings
settings = Settings()
