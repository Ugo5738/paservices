"""
Configuration module for the Data Capture Service.
"""

import json
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Settings for the Data Capture Service.
    Loads environment variables, with fallbacks to default values where appropriate.
    All environment variables are prefixed with DATA_CAPTURE_SERVICE_.
    """

    # Core service settings
    PROJECT_NAME: str = Field(
        "Data Capture Service",
        alias="DATA_CAPTURE_SERVICE_PROJECT_NAME",
        description="Project name",
    )
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT,
        alias="DATA_CAPTURE_SERVICE_ENVIRONMENT",
        description="Application environment",
    )
    ROOT_PATH: str = Field(
        "/api/v1",
        alias="DATA_CAPTURE_SERVICE_ROOT_PATH",
        description="API root path for reverse proxies",
    )
    LOGGING_LEVEL: str = Field(
        "INFO",
        alias="DATA_CAPTURE_SERVICE_LOGGING_LEVEL",
        description="Logging level",
    )

    # Database configuration
    DATABASE_URL: str = Field(
        ...,
        alias="DATA_CAPTURE_SERVICE_DATABASE_URL",
        description="PostgreSQL connection string",
    )

    # Auth Service connection
    AUTH_SERVICE_URL: str = Field(
        "http://auth_service:8000/api/v1",
        alias="DATA_CAPTURE_SERVICE_AUTH_SERVICE_URL",
        description="Auth Service URL for token acquisition",
    )

    # Super ID Service connection
    SUPER_ID_SERVICE_URL: str = Field(
        "http://super_id_service:8000/api/v1",
        alias="DATA_CAPTURE_SERVICE_SUPER_ID_SERVICE_URL",
        description="Super ID Service URL for UUID generation",
    )

    # JWT configuration for auth with other services
    M2M_CLIENT_ID: str = Field(
        ...,
        alias="DATA_CAPTURE_SERVICE_M2M_CLIENT_ID",
        description="Client ID for machine-to-machine authentication",
    )
    M2M_CLIENT_SECRET: str = Field(
        ...,
        alias="DATA_CAPTURE_SERVICE_M2M_CLIENT_SECRET",
        description="Client Secret for machine-to-machine authentication",
    )
    M2M_JWT_SECRET_KEY: str = Field(
        ...,
        alias="DATA_CAPTURE_SERVICE_M2M_JWT_SECRET_KEY",
        description="Symmetric secret key for validating M2M JWTs from the Auth Service.",
    )
    M2M_JWT_AUDIENCE: str = Field(
        "paservices_microservices",
        alias="DATA_CAPTURE_SERVICE_M2M_JWT_AUDIENCE",
        description="The audience claim expected in M2M JWTs.",
    )
    AUTH_SERVICE_ISSUER: str = Field(
        "paservices_auth_service",
        alias="DATA_CAPTURE_SERVICE_AUTH_SERVICE_ISSUER",
        description="Expected issuer claim for Auth Service tokens.",
    )
    AUTH_SERVICE_JWT_ALGORITHM: str = Field(
        "RS256",
        alias="DATA_CAPTURE_SERVICE_AUTH_SERVICE_JWT_ALGORITHM",
        description="JWT signing algorithm used by the Auth Service.",
    )
    AUTH_SERVICE_JWKS_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_AUTH_SERVICE_JWKS_URL",
        description="Override URL for the Auth Service JWKS endpoint.",
    )

    # --- Firecrawl Baseline Provider ---
    FIRECRAWL_API_KEY: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_FIRECRAWL_API_KEY",
        description="Firecrawl API key. If not set, baseline provider is disabled.",
    )
    FIRECRAWL_AGENT_MAX_CREDITS: int = Field(
        2500,
        alias="DATA_CAPTURE_SERVICE_FIRECRAWL_AGENT_MAX_CREDITS",
        description=(
            "Cap on credits a single /v2/agent run may spend. Set to the "
            "SDK default of 2500 — 500 was too tight for Zoopla (the agent "
            "hit the cap mid-run with 'Refusal: Error: Agent reached max "
            "credits'). Single-page listing extraction is bounded by the "
            "schema and prompt; the timeout (FIRECRAWL_AGENT_TIMEOUT_"
            "SECONDS) is the harder ceiling."
        ),
    )
    FIRECRAWL_AGENT_TIMEOUT_SECONDS: int = Field(
        600,
        alias="DATA_CAPTURE_SERVICE_FIRECRAWL_AGENT_TIMEOUT_SECONDS",
        description=(
            "Max seconds the SDK will wait for an /v2/agent run to reach a "
            "terminal status before returning the in-flight AgentResponse "
            "(then surfaced as PARTIAL). 10 minutes — Spark 1 Mini on "
            "complex listing portals (Zoopla, etc.) can run 3-5 min; the "
            "ceiling gives headroom. The n8n callers (Run AI Fetcher in "
            "WF DC B AIF, Call WF2 in WF DC 1 Main) must allow at least "
            "this long."
        ),
    )

    # --- Motie Adapter ---
    MOTIE_BASE_URL: str = Field(
        "https://api.motie.dev",
        alias="DATA_CAPTURE_SERVICE_MOTIE_BASE_URL",
        description="Motie API base URL.",
    )
    MOTIE_API_TOKEN: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_MOTIE_API_TOKEN",
        description="Motie API bearer token (mtk_...).",
    )
    MOTIE_POLL_TIMEOUT: float = Field(
        1800.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_POLL_TIMEOUT",
        description="Maximum seconds to poll Motie agent session before timeout.",
    )
    MOTIE_POLL_INTERVAL: float = Field(
        5.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_POLL_INTERVAL",
        description="Initial poll interval in seconds.",
    )
    MOTIE_POLL_BACKOFF: float = Field(
        1.5,
        alias="DATA_CAPTURE_SERVICE_MOTIE_POLL_BACKOFF",
        description="Exponential backoff multiplier for polling.",
    )
    MOTIE_POLL_MAX_INTERVAL: float = Field(
        60.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_POLL_MAX_INTERVAL",
        description="Maximum poll interval in seconds (cap).",
    )
    MOTIE_DEPLOY_POLL_TIMEOUT: float = Field(
        180.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_DEPLOY_POLL_TIMEOUT",
        description="Maximum seconds to poll Motie deployment before timeout.",
    )
    MOTIE_DEPLOY_POLL_INTERVAL: float = Field(
        5.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_DEPLOY_POLL_INTERVAL",
        description="Initial poll interval for deployment status in seconds.",
    )
    MOTIE_DEPLOYED_ENDPOINT_TIMEOUT: float = Field(
        30.0,
        alias="DATA_CAPTURE_SERVICE_MOTIE_DEPLOYED_ENDPOINT_TIMEOUT",
        description="Timeout for calling deployed Motie scraper endpoints.",
    )

    # --- Adapter Feature Flags ---
    ADAPTER_MOTIE_ENABLED: bool = Field(
        True,
        alias="DATA_CAPTURE_SERVICE_ADAPTER_MOTIE_ENABLED",
        description="Enable the Motie scraping adapter.",
    )
    ADAPTER_FIRECRAWL_EXTRACT_ENABLED: bool = Field(
        False,
        alias="DATA_CAPTURE_SERVICE_ADAPTER_FIRECRAWL_EXTRACT_ENABLED",
        description="Enable Firecrawl as a full extraction adapter (future).",
    )

    # --- Pipeline Configuration ---
    VALIDATION_GATE_ENABLED: bool = Field(
        True,
        alias="DATA_CAPTURE_SERVICE_VALIDATION_GATE_ENABLED",
        description="Enable the validation gate (compare adapter output vs baseline).",
    )
    COMPLETENESS_ACCEPT_THRESHOLD: float = Field(
        0.85,
        alias="DATA_CAPTURE_SERVICE_COMPLETENESS_ACCEPT_THRESHOLD",
        description="Score above this accepts immediately.",
    )
    COMPLETENESS_FALLBACK_THRESHOLD: float = Field(
        0.7,
        alias="DATA_CAPTURE_SERVICE_COMPLETENESS_FALLBACK_THRESHOLD",
        description="Score below this triggers fallback to next adapter.",
    )
    MAX_RETRIES_PER_ADAPTER: int = Field(
        1,
        alias="DATA_CAPTURE_SERVICE_MAX_RETRIES_PER_ADAPTER",
        description="Retry same adapter this many times before fallback.",
    )

    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        30,
        alias="DATA_CAPTURE_SERVICE_RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="Rate limit for API requests per minute",
    )

    # Redis configuration (for rate limiting and caching)
    REDIS_URL: str = Field(
        "redis://localhost:6379/0",
        alias="DATA_CAPTURE_SERVICE_REDIS_URL",
        description="Redis URL for caching and rate limiting",
    )

    # CORS settings
    CORS_ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        alias="DATA_CAPTURE_SERVICE_CORS_ALLOW_ORIGINS",
        description="List of origins that are allowed to make cross-origin requests",
    )

    # Status notification and S3 configuration
    STATUS_WEBHOOK_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_WEBHOOK_URL",
        description="Webhook URL to receive workflow status updates.",
    )
    STATUS_WEBHOOK_HEADERS: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_WEBHOOK_HEADERS",
        description="JSON object of HTTP headers for webhook notifications.",
    )
    STATUS_S3_BUCKET_NAME: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_S3_BUCKET_NAME",
        description="S3 bucket where workflow status snapshots are written.",
    )
    STATUS_S3_REGION: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_S3_REGION",
        description="AWS region that hosts the status snapshot bucket.",
    )
    STATUS_S3_PREFIX: str = Field(
        "data_capture/status",
        alias="DATA_CAPTURE_SERVICE_STATUS_S3_PREFIX",
        description="Key prefix within the S3 bucket for workflow snapshots.",
    )
    STATUS_S3_PUBLIC_BASE_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_S3_PUBLIC_BASE_URL",
        description="Optional base URL for public links to snapshot files.",
    )
    STATUS_S3_ENDPOINT_URL: Optional[str] = Field(
        None,
        alias="DATA_CAPTURE_SERVICE_STATUS_S3_ENDPOINT_URL",
        description="Optional custom endpoint URL for S3-compatible storage.",
    )

    # Optional AWS credentials (falls back to default provider chain if unset)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        None, alias="DATA_CAPTURE_SERVICE_AWS_ACCESS_KEY_ID"
    )
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        None, alias="DATA_CAPTURE_SERVICE_AWS_SECRET_ACCESS_KEY"
    )
    AWS_SESSION_TOKEN: Optional[str] = Field(
        None, alias="DATA_CAPTURE_SERVICE_AWS_SESSION_TOKEN"
    )

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
                f"DATA_CAPTURE_SERVICE_STATUS_WEBHOOK_HEADERS must be valid JSON. {exc}"
            ) from exc
        if not isinstance(headers, dict):
            raise ValueError(
                "DATA_CAPTURE_SERVICE_STATUS_WEBHOOK_HEADERS must decode to a JSON object."
            )
        return {str(key): str(value) for key, value in headers.items()}

    def status_notifications_enabled(self) -> bool:
        return bool(self.STATUS_S3_BUCKET_NAME)

    def firecrawl_enabled(self) -> bool:
        return bool(self.FIRECRAWL_API_KEY)

    def motie_enabled(self) -> bool:
        return self.ADAPTER_MOTIE_ENABLED and bool(self.MOTIE_API_TOKEN)

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
