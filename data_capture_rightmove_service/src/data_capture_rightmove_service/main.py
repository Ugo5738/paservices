"""
Main application entry point for the Data Capture Rightmove Service.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers.health_router import router as health_router
from .routers.property_router import router as property_router
from .routers.workflow_status_router import router as workflow_status_router
from .supabase_client import init_supabase_clients
from .utils.logging_config import LoggingMiddleware, logger, setup_logging
from .utils.rate_limiting import setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager with robust initialization and shutdown.

    Handles startup and shutdown sequences with proper error handling.
    """
    logger.info("Application startup sequence initiated.")

    # Initialize app-wide resources and connections
    try:
        await init_supabase_clients()
        logger.info("Supabase clients initialized successfully")
    except Exception as e:
        logger.error(
            f"Failed to initialize Supabase clients: {e.__class__.__name__}: {str(e)}"
        )

    # Initialize startup timestamp for health checks
    app.state.startup_time = time.time()
    logger.info("Application startup complete.")

    # Yield control back to the application
    yield

    # Application Shutdown
    logger.info("Application shutdown sequence initiated.")
    logger.info("Application shutdown complete.")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Data Capture Rightmove Service",
    description=(
        "Service for fetching property data from Rightmove via RapidAPI "
        "and storing it in a structured database."
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
app.include_router(property_router, tags=["Properties"])
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "data_capture_rightmove_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
        log_level=settings.LOGGING_LEVEL.lower(),
    )
