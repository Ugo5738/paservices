"""
Configuration module for the Data Capture Rightmove Service.
"""

import os
from enum import Enum
from typing import Any, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Settings for the Data Capture Rightmove Service.
    Loads environment variables, with fallbacks to default values where appropriate.
    All environment variables are prefixed with DATA_CAPTURE_RIGHTMOVE_SERVICE_.
    """

    # Core service settings
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_ENVIRONMENT",
        description="Application environment",
    )
    ROOT_PATH: str = Field(
        "/api/v1",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_ROOT_PATH",
        description="API root path for reverse proxies",
    )
    LOGGING_LEVEL: str = Field(
        "INFO",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_LOGGING_LEVEL",
        description="Logging level",
    )

    # Database configuration
    DATABASE_URL: str = Field(
        ...,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_DATABASE_URL",
        description="PostgreSQL connection string",
    )

    SUPABASE_URL: str = Field(..., alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(
        ..., alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_ANON_KEY"
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ..., alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_SERVICE_ROLE_KEY"
    )

    # Auth Service connection
    AUTH_SERVICE_URL: str = Field(
        "http://auth-service:8000/api/v1",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_URL",
        description="Auth Service URL for token acquisition",
    )

    # Super ID Service connection
    SUPER_ID_SERVICE_URL: str = Field(
        "http://super-id-service:8000/api/v1",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPER_ID_SERVICE_URL",
        description="Super ID Service URL for UUID generation",
    )

    # JWT configuration for auth with other services
    M2M_CLIENT_ID: str = Field(
        ...,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID",
        description="Client ID for machine-to-machine authentication",
    )
    M2M_CLIENT_SECRET: str = Field(
        ...,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET",
        description="Client Secret for machine-to-machine authentication",
    )

    # RapidAPI configuration
    RAPID_API_KEY: str = Field(
        ...,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_KEY",
        description="RapidAPI key for accessing Rightmove API",
    )
    RAPID_API_HOST: str = Field(
        "uk-real-estate-rightmove.p.rapidapi.com",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_HOST",
        description="RapidAPI host for Rightmove API",
    )

    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        30,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="Rate limit for API requests per minute",
    )

    # Redis configuration (for rate limiting and caching)
    REDIS_URL: str = Field(
        "redis://localhost:6379/0",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_REDIS_URL",
        description="Redis URL for caching and rate limiting",
    )

    # CORS settings
    CORS_ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_CORS_ALLOW_ORIGINS",
        description="List of origins that are allowed to make cross-origin requests",
    )

    # Rightmove API endpoints
    RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT: str = Field(
        "/properties/details",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT",
        description="Rightmove API endpoint for property details",
    )
    RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT: str = Field(
        "/buy/property-for-sale",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT",
        description="Rightmove API endpoint for property for sale",
    )

    # Data fetch configuration
    BATCH_SIZE: int = Field(
        10,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_BATCH_SIZE",
        description="Number of properties to fetch in a batch",
    )
    FETCH_INTERVAL_SECONDS: int = Field(
        3600,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_FETCH_INTERVAL_SECONDS",
        description="Interval between data fetch operations in seconds",
    )

    @field_validator("DATABASE_URL")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # Add any database URL validation logic here if needed
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


# Create a global instance of the settings
settings = Settings()
