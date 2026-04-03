import json
from enum import Enum
from typing import Any, Dict, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Settings for the PA MCP Service.
    Loads environment variables, with fallbacks to default values where appropriate.
    """

    model_config = SettingsConfigDict(
        env_prefix="PA_MCP_",  # All env vars should be prefixed with PA_MCP_
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core settings
    PROJECT_NAME: str = Field(
        "PA MCP Service",
        alias="PA_MCP_PROJECT_NAME",
        description="Project name",
    )
    ENVIRONMENT: Environment = Field(
        Environment.DEVELOPMENT,
        alias="PA_MCP_ENVIRONMENT",
        description="Application environment",
    )
    LOGGING_LEVEL: str = Field(
        "INFO",
        alias="PA_MCP_LOGGING_LEVEL",
        description="Logging level",
    )

    # Database configuration (kept consistent with other services)
    DATABASE_URL: str = Field(
        "postgresql+psycopg://postgres:postgres@supabase_db_paservices:5432/pa_mcp",
        alias="PA_MCP_DATABASE_URL",
        description="PostgreSQL connection string",
    )

    # Supabase configuration
    SUPABASE_URL: str = Field(
        "http://supabase_kong_paservices:8000",
        alias="PA_MCP_SUPABASE_URL",
        description="Supabase project URL",
    )
    SUPABASE_ANON_KEY: str = Field(
        "your_supabase_anon_key",
        alias="PA_MCP_SUPABASE_ANON_KEY",
        description="Supabase anon key",
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        "your_supabase_service_role_key",
        alias="PA_MCP_SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key",
    )

    # CORS settings
    CORS_ALLOW_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        alias="PA_MCP_CORS_ALLOW_ORIGINS",
        description="List of origins that are allowed to make cross-origin requests",
    )

    # M2M credentials for calling auth + super_id services
    M2M_CLIENT_ID: str = Field(
        "",
        validation_alias="PA_MCP_M2M_CLIENT_ID",
        description="M2M client ID for authenticating with auth service",
    )
    M2M_CLIENT_SECRET: str = Field(
        "",
        validation_alias="PA_MCP_M2M_CLIENT_SECRET",
        description="M2M client secret for authenticating with auth service",
    )

    # Service URLs
    AUTH_SERVICE_URL: str = Field(
        "http://localhost:8001/api/v1",
        validation_alias="PA_MCP_AUTH_SERVICE_URL",
        description="Base URL for the Auth Service",
    )
    SUPER_ID_SERVICE_URL: str = Field(
        "http://localhost:8002/api/v1",
        validation_alias="PA_MCP_SUPER_ID_SERVICE_URL",
        description="Base URL for the Super ID Service",
    )
    N8N_SUPERSAMI_TRIGGER_URL: str = Field(
        "http://n8n:5678/webhook/supersami-trigger",
        validation_alias="PA_MCP_N8N_SUPERSAMI_TRIGGER_URL",
        description="Webhook URL for kicking off the n8n SuperSami workflow",
    )
    WORKFLOW_CALLBACK_URL: str = Field(
        "http://pa_mcp:8765/api/analysis/callback",
        validation_alias="PA_MCP_WORKFLOW_CALLBACK_URL",
        description="Callback endpoint n8n should POST final analysis results to",
    )

    # ScaleKit Configuration
    SCALEKIT_ENVIRONMENT_URL: str = Field(
        ...,
        alias="PA_MCP_SCALEKIT_ENVIRONMENT_URL",
        description="ScaleKit environment URL",
    )
    SCALEKIT_CLIENT_ID: str = Field(
        ..., alias="PA_MCP_SCALEKIT_CLIENT_ID", description="ScaleKit client ID"
    )
    SCALEKIT_CLIENT_SECRET: str = Field(
        ..., alias="PA_MCP_SCALEKIT_CLIENT_SECRET", description="ScaleKit client secret"
    )
    SCALEKIT_RESOURCE_METADATA_URL: str = Field(
        ...,
        alias="PA_MCP_SCALEKIT_RESOURCE_METADATA_URL",
        description="ScaleKit resource metadata URL",
    )
    SCALEKIT_AUDIENCE_NAME: str = Field(
        ..., alias="PA_MCP_SCALEKIT_AUDIENCE_NAME", description="ScaleKit audience name"
    )
    METADATA_JSON_RESPONSE: Dict[str, Any] = Field(
        ...,
        alias="PA_MCP_METADATA_JSON_RESPONSE",
        description="Metadata JSON response, parsed into a dictionary",
    )

    SCALEKIT_RESOURCE_NAME: str = Field(
        "http://localhost:8765/mcp",  # NO trailing slash (canonical)
        alias="PA_MCP_SCALEKIT_RESOURCE_NAME",
    )
    SCALEKIT_RESOURCE_DOCS_URL: str = Field(
        "http://localhost:8765/mcp/docs",
        alias="PA_MCP_SCALEKIT_RESOURCE_DOCS_URL",
    )
    SCALEKIT_AUTHORIZATION_SERVERS: str = Field(
        "...",
        alias="PA_MCP_SCALEKIT_AUTHORIZATION_SERVERS",
    )

    # Per-service n8n workflow webhook URLs
    N8N_DATA_CAPTURE_RIGHTMOVE_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_DATA_CAPTURE_RIGHTMOVE_URL",
        description="Webhook URL for the Rightmove data capture n8n workflow",
    )
    N8N_DATA_CAPTURE_MOTIE_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_DATA_CAPTURE_MOTIE_URL",
        description="Webhook URL for the Motie data capture n8n workflow",
    )
    N8N_FLOORPLAN_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_FLOORPLAN_URL",
        description="Webhook URL for the floorplan analysis n8n workflow",
    )
    N8N_IMAGE_CONDITION_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_IMAGE_CONDITION_URL",
        description="Webhook URL for the image condition analysis n8n workflow",
    )
    N8N_ORCHESTRATOR_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_ORCHESTRATOR_URL",
        description="Webhook URL for the v1 orchestrator n8n workflow (parallel only)",
    )
    N8N_ORCHESTRATOR_V2_URL: str = Field(
        "",
        validation_alias="PA_MCP_N8N_ORCHESTRATOR_V2_URL",
        description="Webhook URL for the v2 orchestrator n8n workflow (handles sequential dependencies)",
    )

    @field_validator("METADATA_JSON_RESPONSE", mode="before")
    @classmethod
    def parse_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("METADATA_JSON_RESPONSE contains invalid JSON")
        return value

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if the application is running in development."""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """Check if the application is running in test mode."""
        return self.ENVIRONMENT == Environment.TESTING


settings = Settings()
