"""
Super ID Service - Main application entry point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import settings
from .db import AsyncSessionLocal
from .routers.health_router import router as health_router
from .routers.super_id_router import router as super_id_router
from .utils.logging_config import LoggingMiddleware, logger, setup_logging
from .utils.rate_limiting import setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("Application startup sequence initiated.")
    # Perform a quick database connection test on startup.
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed on startup: {e}", exc_info=True)

    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown complete.")


# Initialize FastAPI app
app = FastAPI(
    title="Super ID Service",
    description="Service for generating and recording unique identifiers (UUIDs)",
    version="0.1.0",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# Setup logging configuration
setup_logging(app)

# Add logging middleware
app.add_middleware(LoggingMiddleware)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # Check if the detail is a dict, which indicates our custom MCP response
    if isinstance(exc.detail, dict) and "status" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    # Default behavior for all other HTTPErrors
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


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

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(super_id_router, prefix="/super_ids", tags=["Super IDs"])
