"""
Configuration module for the Data Capture Rightmove Service.
"""

import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional

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
    PROJECT_NAME: str = Field(
        "Data Capture Rightmove Service",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_PROJECT_NAME",
        description="Project name",
    )
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
        "http://auth_service:8000/api/v1",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_URL",
        description="Auth Service URL for token acquisition",
    )

    # Super ID Service connection
    SUPER_ID_SERVICE_URL: str = Field(
        "http://super_id_service:8000/api/v1",
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
    M2M_JWT_SECRET_KEY: str = Field(
        ...,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_JWT_SECRET_KEY",
        description="Symmetric secret key for validating M2M JWTs from the Auth Service.",
    )
    M2M_JWT_AUDIENCE: str = Field(
        "paservices_microservices",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_JWT_AUDIENCE",
        description="The audience claim expected in M2M JWTs.",
    )
    AUTH_SERVICE_ISSUER: str = Field(
        "paservices_auth_service",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_ISSUER",
        description="Expected issuer claim for Auth Service tokens.",
    )
    AUTH_SERVICE_JWT_ALGORITHM: str = Field(
        "RS256",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_JWT_ALGORITHM",
        description="JWT signing algorithm used by the Auth Service.",
    )
    AUTH_SERVICE_JWKS_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_JWKS_URL",
        description="Override URL for the Auth Service JWKS endpoint.",
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

    # Status notification and S3 configuration
    STATUS_WEBHOOK_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_URL",
        description="Webhook URL to receive workflow status updates.",
    )
    STATUS_WEBHOOK_HEADERS: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS",
        description="JSON object of HTTP headers to include when sending webhook notifications.",
    )
    STATUS_S3_BUCKET_NAME: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_BUCKET_NAME",
        description="S3 bucket where workflow status snapshots are written.",
    )
    STATUS_S3_REGION: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_REGION",
        description="AWS region that hosts the status snapshot bucket.",
    )
    STATUS_S3_PREFIX: str = Field(
        "rightmove/status",
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PREFIX",
        description="Key prefix within the S3 bucket for workflow snapshots.",
    )
    STATUS_S3_PUBLIC_BASE_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PUBLIC_BASE_URL",
        description="Optional base URL used to build public links to snapshot files.",
    )
    STATUS_S3_ENDPOINT_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_ENDPOINT_URL",
        description="Optional custom endpoint URL for S3-compatible storage.",
    )

    # Optional AWS credentials (falls back to default provider chain if unset)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        None, alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AWS_ACCESS_KEY_ID"
    )
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        None, alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AWS_SECRET_ACCESS_KEY"
    )
    AWS_SESSION_TOKEN: Optional[str] = Field(
        None, alias="DATA_CAPTURE_RIGHTMOVE_SERVICE_AWS_SESSION_TOKEN"
    )

    @field_validator("DATABASE_URL")
    def validate_database_url(cls, v: str, info: Any) -> str:
        # Add any database URL validation logic here if needed
        return v

    @field_validator("STATUS_WEBHOOK_HEADERS")
    def parse_webhook_headers(cls, v: Optional[str]) -> Optional[Dict[str, str]]:
        if v in (None, "", {}):
            return None
        if isinstance(v, dict):
            return {str(key): str(value) for key, value in v.items()}
        try:
            headers = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS must be valid JSON. {exc}"
            ) from exc
        if not isinstance(headers, dict):
            raise ValueError(
                "DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS must decode to a JSON object."
            )
        return {str(key): str(value) for key, value in headers.items()}

    def status_notifications_enabled(self) -> bool:
        return bool(self.STATUS_S3_BUCKET_NAME)

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
