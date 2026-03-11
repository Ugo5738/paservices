"""
Main application entry point for the Data Capture Service.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers.adapter_router import router as adapter_router
from .routers.health_router import router as health_router
from .routers.data_capture_router import router as data_capture_router
from .utils.logging_config import LoggingMiddleware, logger, setup_logging
from .utils.rate_limiting import setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager with robust initialization and shutdown.

    Handles startup and shutdown sequences with proper error handling.
    """
    logger.info("Data Capture Service startup sequence initiated.")

    # Initialize startup timestamp for health checks
    app.state.startup_time = time.time()

    # Log adapter and provider status
    logger.info(f"Firecrawl baseline provider: {'enabled' if settings.firecrawl_enabled() else 'disabled'}")
    logger.info(f"Motie adapter: {'enabled' if settings.motie_enabled() else 'disabled'}")
    logger.info(f"Validation gate: {'enabled' if settings.VALIDATION_GATE_ENABLED else 'disabled'}")
    logger.info(
        f"Completeness thresholds: accept={settings.COMPLETENESS_ACCEPT_THRESHOLD}, "
        f"fallback={settings.COMPLETENESS_FALLBACK_THRESHOLD}"
    )

    logger.info("Data Capture Service startup complete.")

    # Yield control back to the application
    yield

    # Application Shutdown
    logger.info("Data Capture Service shutdown sequence initiated.")
    logger.info("Data Capture Service shutdown complete.")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Data Capture Service",
    description=(
        "Agnostic property data_capture service with pluggable adapters. "
        "Supports Motie AI scraping with Firecrawl baseline validation."
    ),
    version="0.1.0",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# Track app startup time for uptime monitoring in health checks
app.startup_time = time.time()

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
app.include_router(data_capture_router, tags=["DataCapture"])
app.include_router(adapter_router, tags=["Adapters"])


# --- Exception Handlers ---


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "data_capture_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
        log_level=settings.LOGGING_LEVEL.lower(),
    )
