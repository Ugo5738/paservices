"""
Main application entry point for the Data Capture Rightmove Service.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from floorplan_service.config import settings
from floorplan_service.routers.floorplan_router import router as floorplan_router
from floorplan_service.routers.health_router import router as health_router
from floorplan_service.routers.workflow_status_router import (
    router as workflow_status_router,
)
from floorplan_service.utils.logging_config import (
    LoggingMiddleware,
    logger,
    setup_logging,
)
from floorplan_service.utils.rate_limiting import setup_rate_limiting


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

# Setup logging configuration
setup_logging(app)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup rate limiting
setup_rate_limiting(app)


# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(floorplan_router, prefix="/floorplans", tags=["Floorplans"])
app.include_router(workflow_status_router, tags=["Workflow Status"])


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
