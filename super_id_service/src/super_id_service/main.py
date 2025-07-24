"""
Super ID Service - Main application entry point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from super_id_service.config import settings
from super_id_service.db import AsyncSessionLocal, get_db
from super_id_service.routers.health_router import router as health_router
from super_id_service.routers.super_id_router import router as super_id_router
from super_id_service.utils.logging_config import logger, setup_logging


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
    logger.info("Application shutdown sequence initiated.")
    logger.info("Application shutdown complete.")


# Initialize FastAPI app
app = FastAPI(
    title="Super ID Service",
    description="Service for generating and recording unique identifiers (UUIDs)",
    version="0.1.0",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# Setup logging
setup_logging(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(super_id_router, prefix="/super_ids", tags=["Super IDs"])
