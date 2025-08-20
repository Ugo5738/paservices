"""
Main application entry point for the Data Capture Rightmove Service.
"""

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from floorplan_service.config import settings
from floorplan_service.routers.floorplan_router import router as floorplan_router
from floorplan_service.routers.health_router import router as health_router
from floorplan_service.utils.logging_config import configure_logging, logger
from floorplan_service.utils.rate_limiting import limiter
from floorplan_service.utils.security import validate_token

# Configure logging using our custom configuration
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("Application startup sequence initiated.")
    app.state.startup_time = time.time()
    yield
    logger.info("Application shutdown sequence initiated.")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Floorplan Service",
    description="Handles the orchestration of floorplan analysis and data storage.",
    version="0.1.0",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add rate limiter middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(floorplan_router, prefix="/floorplans", tags=["Floorplans"])


# Add exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler for consistent error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_type": "HTTPException"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Validation exception handler for consistent error responses."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_type": "ValidationError"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler for consistent error responses."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "error_type": str(type(exc).__name__),
        },
    )
