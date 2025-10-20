import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

# from mcp.server.fastmcp import FastMCP  # official MCP SDK FastMCP
from fastmcp import FastMCP
from sqlalchemy import text
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings
from .db import AsyncSessionLocal
from .routers.health_router import router as health_router
from .routers.super_id_router import router as super_id_router
from .utils.logging_config import LoggingMiddleware, logger, setup_logging
from .utils.rate_limiting import setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application's original lifecycle manager for DB connections etc."""

    logger.info("Application startup sequence initiated.")
    # Perform a quick database connection test on startup.
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed on startup: {e}", exc_info=True)

    yield
    logger.info("Application shutdown complete.")


# FastAPI app
app = FastAPI(
    title="Super ID Service API",
    description="Service for generating and recording unique identifiers (UUIDs)",
    version="0.1.0",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# Setup logging configuration
setup_logging(app)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup rate limiting
setup_rate_limiting(app)


app.include_router(health_router, tags=["Health"])
app.include_router(super_id_router, prefix="/super_ids", tags=["Super IDs (REST API)"])


# Resource Metadata
@app.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata():
    return JSONResponse(
        {
            "resource": settings.SUPER_ID_SERVICE_RESOURCE_URL,
            "authorization_servers": [settings.AUTH_SERVICE_ISSUER],
            "scopes_supported": ["super_id:generate"],
            "bearer_methods_supported": ["header"],
            "resource_documentation": settings.SUPER_ID_SERVICE_DOCUMENTATION_URL,
            "mcp_protocol_version": "2025-06-18",
            "resource_type": "mcp-server",
        }
    )
