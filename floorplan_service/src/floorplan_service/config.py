"""
Configuration module for the Floorplan Service.
"""

import os
from enum import Enum
from typing import Any, ClassVar, List, Optional

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
    All environment variables are prefixed with FLOORPLAN_SERVICE_.
    """

    # Core service settings
    PROJECT_NAME: str = Field(
        "Floorplan Service",
        alias="FLOORPLAN_SERVICE_PROJECT_NAME",
        description="Project name",
    )
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT,
        alias="FLOORPLAN_SERVICE_ENVIRONMENT",
        description="Application environment",
    )
    ROOT_PATH: str = Field(
        "/api/v1",
        alias="FLOORPLAN_SERVICE_ROOT_PATH",
        description="API root path for reverse proxies",
    )
    LOGGING_LEVEL: str = Field(
        "INFO",
        alias="FLOORPLAN_SERVICE_LOGGING_LEVEL",
        description="Logging level",
    )

    # Database configuration
    DATABASE_URL: str = Field(
        ...,
        alias="FLOORPLAN_SERVICE_DATABASE_URL",
        description="PostgreSQL connection string",
    )

    # External Services
    AUTH_SERVICE_URL: str = Field(
        "http://auth_service:8000/api/v1",
        alias="FLOORPLAN_SERVICE_AUTH_SERVICE_URL",
        description="Auth Service URL for token acquisition",
    )

    SUPER_ID_SERVICE_URL: str = Field(
        "http://super_id_service:8000/api/v1",
        alias="FLOORPLAN_SERVICE_SUPER_ID_SERVICE_URL",
        description="Super ID Service URL for UUID generation",
    )

    FLOORPLAN_ANALYZER_URL: str = Field(
        "http://floorplan_analyzer:8000/api/v1",
        alias="FLOORPLAN_SERVICE_INDIAN_FLOORPLAN_ANALYZER_URL",
        description="Floorplan Analyzer Service URL for floorplan analysis",
    )
    FLOORPLAN_WEBHOOK_URL: str = Field(
        "http://floorplan_service:8000/api/v1/webhook",
        alias="FLOORPLAN_SERVICE_FLOORPLAN_WEBHOOK_URL",
        description="This service's own webhook endpoint",
    )

    # AWS Settings (for S3 operations like GIF conversion)
    AWS_ACCESS_KEY_ID: str = Field(
        "",
        alias="FLOORPLAN_SERVICE_AWS_ACCESS_KEY_ID",
        description="AWS Access Key ID for S3 operations",
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        "",
        alias="FLOORPLAN_SERVICE_AWS_SECRET_ACCESS_KEY",
        description="AWS Secret Access Key for S3 operations",
    )
    AWS_STORAGE_BUCKET_NAME: str = Field(
        "",
        alias="FLOORPLAN_SERVICE_AWS_STORAGE_BUCKET_NAME",
        description="AWS Storage Bucket Name for S3 operations",
    )
    AWS_S3_FILE_OVERWRITE: ClassVar[bool] = False
    AWS_DEFAULT_ACL: ClassVar[Optional[str]] = None
    AWS_S3_OBJECT_PARAMETERS: ClassVar[dict[str, str]] = {
        "CacheControl": "max-age-86400"
    }
    AWS_LOCATION: ClassVar[str] = "static"
    AWS_QUERYSTRING_AUTH: ClassVar[bool] = False
    AWS_HEADERS: ClassVar[dict[str, str]] = {
        "Access-Control-Allow-Origin": "*",
    }
    AWS_S3_REGION_NAME: str = Field(
        "us-east-1",
        alias="FLOORPLAN_SERVICE_AWS_S3_REGION_NAME",
        description="AWS S3 Region Name for S3 operations",
    )

    # Celery/Background Task Runner Settings
    CELERY_BROKER_URL: str = Field(
        "redis://redis:6379/0",
        alias="FLOORPLAN_SERVICE_CELERY_BROKER_URL",
        description="Celery Broker URL for background task processing",
    )
    CELERY_RESULT_BACKEND: str = Field(
        "redis://redis:6379/0",
        alias="FLOORPLAN_SERVICE_CELERY_RESULT_BACKEND",
        description="Celery Result Backend URL for background task processing",
    )

    # JWT configuration for auth with other services
    M2M_CLIENT_ID: str = Field(
        ...,
        alias="FLOORPLAN_SERVICE_M2M_CLIENT_ID",
        description="Client ID for machine-to-machine authentication",
    )
    M2M_CLIENT_SECRET: str = Field(
        ...,
        alias="FLOORPLAN_SERVICE_M2M_CLIENT_SECRET",
        description="Client Secret for machine-to-machine authentication",
    )
    M2M_JWT_SECRET_KEY: str = Field(
        ...,
        alias="FLOORPLAN_SERVICE_M2M_JWT_SECRET_KEY",
        description="Symmetric secret key for validating M2M JWTs from the Auth Service.",
    )
    M2M_JWT_AUDIENCE: str = Field(
        "paservices_microservices",
        alias="FLOORPLAN_SERVICE_M2M_JWT_AUDIENCE",
        description="The audience claim expected in M2M JWTs.",
    )

    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        30,
        alias="FLOORPLAN_SERVICE_RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="Rate limit for API requests per minute",
    )

    # Redis configuration (for rate limiting and caching)
    REDIS_URL: str = Field(
        "redis://localhost:6379/0",
        alias="FLOORPLAN_SERVICE_REDIS_URL",
        description="Redis URL for caching and rate limiting",
    )

    # CORS settings
    CORS_ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        alias="FLOORPLAN_SERVICE_CORS_ALLOW_ORIGINS",
        description="List of origins that are allowed to make cross-origin requests",
    )

    # Data fetch configuration
    BATCH_SIZE: int = Field(
        10,
        alias="FLOORPLAN_SERVICE_BATCH_SIZE",
        description="Number of properties to fetch in a batch",
    )
    FETCH_INTERVAL_SECONDS: int = Field(
        3600,
        alias="FLOORPLAN_SERVICE_FETCH_INTERVAL_SECONDS",
        description="Interval between data fetch operations in seconds",
    )

    @property
    def AWS_S3_CUSTOM_DOMAIN(self) -> str:
        return f"{self.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

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
