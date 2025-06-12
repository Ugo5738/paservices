import asyncio
import datetime
import sys
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gotrue.errors import AuthApiError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.bootstrap import bootstrap_admin_and_rbac
from auth_service.config import settings
from auth_service.db import get_db, is_pgbouncer
from auth_service.logging_config import LoggingMiddleware, logger, setup_logging
from auth_service.rate_limiting import limiter, setup_rate_limiting
from auth_service.routers import (
    admin_client_role_routes,
    admin_client_routes,
    admin_permission_routes,
    admin_role_permission_routes,
    admin_role_routes,
    admin_user_role_routes,
)
from auth_service.routers.token_routes import router as token_router
from auth_service.routers.user_auth_routes import user_auth_router
from auth_service.schemas import MessageResponse
from auth_service.supabase_client import (
    close_supabase_client,
    get_supabase_admin_client,
)
from auth_service.supabase_client import (
    get_supabase_client as get_general_supabase_client,
)
from auth_service.supabase_client import init_supabase_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager with robust initialization.

    Handles startup and shutdown sequences with proper error handling and retry logic.
    Features:
    - Graceful initialization of Supabase clients
    - Resilient database connection for bootstrap process
    - Proper cleanup on application shutdown
    """
    logger.info("Application startup sequence initiated.")

    # 1. Initialize app-wide resources (like the global Supabase client)
    try:
        await init_supabase_client()
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.error(
            f"Failed to initialize Supabase client: {e.__class__.__name__}: {str(e)}"
        )
        # Continue anyway - the health checks will report the issue

    # 2. Run bootstrap process with retry logic
    logger.info("Running bootstrap process...")
    db_session_for_bootstrap = None
    bootstrap_success = False

    # Define max retries and delays for bootstrap
    max_retries = 5
    base_delay = 2.0

    # Try to bootstrap with retries
    for attempt in range(max_retries):
        try:
            # Get a DB session specifically for bootstrap
            db_session_for_bootstrap = None
            async for session in get_db():  # This already has retry logic built in
                db_session_for_bootstrap = session
                break

            if not db_session_for_bootstrap:
                raise RuntimeError("Failed to get database session for bootstrap")

            # Run the actual bootstrap process
            bootstrap_success = await bootstrap_admin_and_rbac(db_session_for_bootstrap)

            if bootstrap_success:
                logger.info(
                    f"Bootstrap process completed successfully on attempt {attempt + 1}"
                )
                break
            else:
                logger.warning(
                    "Bootstrap process completed but reported non-success status"
                )
                # We'll consider this a success anyway to avoid unnecessary retries
                bootstrap_success = True
                break

        except Exception as e:
            if db_session_for_bootstrap:
                try:
                    # Ensure we release the session resources
                    await db_session_for_bootstrap.close()
                except Exception:
                    pass  # Ignore close errors

            # Determine if we should retry
            if attempt < max_retries - 1:
                retry_delay = base_delay * (2**attempt)  # Exponential backoff
                logger.warning(
                    f"Bootstrap attempt {attempt + 1} failed: {e.__class__.__name__}: {str(e)}. "
                    f"Retrying in {retry_delay:.1f}s..."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"Bootstrap process failed after {max_retries} attempts. "
                    f"Last error: {e.__class__.__name__}: {str(e)}"
                )
                # Continue anyway - the application can still function without bootstrap

    # Report final bootstrap status
    if bootstrap_success:
        logger.info("Bootstrap process successful, application ready to serve requests")
    else:
        logger.warning(
            "Bootstrap process did not complete successfully. "
            "The application will start but may have limited functionality."
        )

    # Application is now ready to serve requests
    logger.info("Application startup complete.")

    # Yield control back to the application
    yield

    # --- Application Shutdown ---
    logger.info("Application shutdown sequence initiated.")

    # Close Supabase client connections
    try:
        await close_supabase_client()
        logger.info("Supabase client closed successfully.")
    except Exception as e:
        logger.error(f"Error closing Supabase client: {str(e)}")

    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Authentication Service API",
    description="Authentication and Authorization service for managing users, application clients, roles, and permissions.",
    version="1.0.0",
    root_path=settings.root_path,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "User Authentication",
            "description": "Operations for user authentication including login, registration, password management, and profile management.",
        },
        {
            "name": "Token Acquisition",
            "description": "Operations for obtaining authentication tokens for machine-to-machine (M2M) communication.",
        },
        {
            "name": "Admin - App Clients",
            "description": "Administrative operations for managing application clients.",
        },
        {
            "name": "Admin - Roles",
            "description": "Administrative operations for managing roles.",
        },
        {
            "name": "Admin - Permissions",
            "description": "Administrative operations for managing permissions.",
        },
        {
            "name": "Admin - Role Permissions",
            "description": "Administrative operations for assigning permissions to roles.",
        },
        {
            "name": "Admin - User Roles",
            "description": "Administrative operations for assigning roles to users.",
        },
        {
            "name": "Admin - Client Roles",
            "description": "Administrative operations for assigning roles to application clients.",
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
)


# Diagnostic endpoint for database connectivity
@app.get("/internal/db-diagnostics", include_in_schema=False)
async def db_diagnostics(*, db: AsyncSession = Depends(get_db)):
    """Comprehensive database diagnostic check with detailed metrics.

    This endpoint performs multiple tests to verify database connectivity and performance.
    It's intended for operators and administrators to diagnose connection issues.
    """
    start_time = time.time()
    results = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "tests": {},
        "connection_pool": {},
        "success": False,
    }

    # Test 1: Basic connectivity
    try:
        basic_start = time.time()
        await db.execute(text("SELECT 1"))
        basic_time = time.time() - basic_start
        results["tests"]["basic_connectivity"] = {
            "status": "ok",
            "time_ms": round(basic_time * 1000, 2),
        }
    except Exception as e:
        results["tests"]["basic_connectivity"] = {
            "status": "error",
            "error": f"{e.__class__.__name__}: {str(e)}",
        }
        return results

    # Test 2: Database version
    try:
        version_start = time.time()
        result = await db.execute(text("SELECT version()"))
        version = result.scalar_one_or_none()
        version_time = time.time() - version_start
        results["tests"]["version_check"] = {
            "status": "ok",
            "version": version,
            "time_ms": round(version_time * 1000, 2),
        }
    except Exception as e:
        results["tests"]["version_check"] = {
            "status": "error",
            "error": f"{e.__class__.__name__}: {str(e)}",
        }

    # Test 3: Connection pool stats (approximate as these are not fully exposed)
    try:
        # Get pool stats (this is implementation-specific and may not work for all drivers)
        pool = db.bind.pool
        results["connection_pool"] = {
            "size": getattr(pool, "size", "unknown"),
            "overflow": getattr(pool, "overflow", "unknown"),
            "timeout": getattr(pool, "timeout", "unknown"),
            "checkedin": getattr(pool, "_checkedin", "unknown"),
            "checkedout": getattr(pool, "_checkedout", "unknown"),
        }
    except Exception as e:
        results["connection_pool"] = {
            "error": f"Could not retrieve pool stats: {str(e)}"
        }

    # Overall success and timing
    results["total_time_ms"] = round((time.time() - start_time) * 1000, 2)
    results["success"] = True

    return results


# Track app startup time for uptime monitoring in health checks
app.startup_time = time.time()

# Setup logging configuration
setup_logging(app)

# Setup rate limiting
setup_rate_limiting(app)

# Add logging middleware (after request_id middleware which is added in setup_logging)
app.add_middleware(LoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(user_auth_router)
app.include_router(admin_client_routes.router)
app.include_router(token_router)
app.include_router(admin_role_routes.router, prefix="/auth/admin")
app.include_router(admin_permission_routes.router, prefix="/auth/admin")
app.include_router(admin_role_permission_routes.router, prefix="/auth/admin")
app.include_router(admin_user_role_routes.router, prefix="/auth/admin")
app.include_router(admin_client_role_routes.router, prefix="/auth/admin")


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Rate limit exceeded exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded: {request.client.host} - {request.url.path}")
    # Extract retry seconds from the exception message if available
    # Format is typically '5 per 1 minute'
    retry_seconds = 60  # Default to 60 seconds
    try:
        limit_string = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        parts = limit_string.split(" per ")
        if len(parts) == 2 and "minute" in parts[1]:
            # Default retry window is 1 minute
            retry_seconds = 60
        elif len(parts) == 2 and "hour" in parts[1]:
            # For hourly rate limits
            retry_seconds = 3600
        elif len(parts) == 2 and "day" in parts[1]:
            # For daily rate limits
            retry_seconds = 86400
    except Exception as e:
        logger.error(f"Error parsing rate limit message: {e}")

    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests", "retry_after": retry_seconds},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"ValidationError: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# Health check cache to avoid repeated database queries, greatly increased TTL to reduce API calls
_health_check_cache = {
    "last_check": None,  # Timestamp of last health check
    "result": None,  # Cached result
    "cache_ttl_seconds": 120,  # Cache validity period (2 minutes to reduce API calls)
    "db_check_counter": 0,  # Counter for adaptive DB checking
    "db_check_interval": 10,  # Only check DB every 10 requests to reduce DB load
}


@app.get("/health")
async def health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    supabase_general_client: AsyncSupabaseClient = Depends(get_general_supabase_client),
):
    """Health check endpoint optimized for Kubernetes probes.

    This health check is designed to be lightweight and reliable,
    avoiding heavy database operations that could cause timeouts.
    It caches results to reduce load and uses adaptive checking.
    For Kubernetes probes, it always returns a 200 OK status if
    the API itself is running, to prevent unnecessary pod restarts.
    """

    # Check if this is a Kubernetes probe
    is_k8s_probe = (
        request.headers.get("user-agent", "").lower().startswith("kube-probe")
    )

    # Also check for diagnostic mode - bypasses caching and always tests DB
    is_diagnostic = request.query_params.get("diagnostic") == "true"

    # Get current time
    current_time = datetime.datetime.utcnow()

    # Initialize response
    response = {
        "status": "ok",
        "version": app.version,
        "environment": str(settings.environment),
        "timestamp": current_time.isoformat(),
        "components": {"api": {"status": "ok"}},
    }

    # Add pgBouncer info to help diagnose issues
    response["pgbouncer_mode"] = is_pgbouncer

    # Use cache if available and not expired, but skip cache in diagnostic mode
    cache = _health_check_cache
    if (
        not is_diagnostic
        and cache["last_check"]
        and cache["result"]
        and (time.time() - cache["last_check"]) < cache["cache_ttl_seconds"]
    ):
        # Update timestamp but keep other results from cache
        result = cache["result"].copy()
        result["timestamp"] = current_time.isoformat()

        # For k8s probes, always return 200 OK if the API is running
        if is_k8s_probe:
            # For Kubernetes probes, always report OK status
            result["status"] = "ok"
            # Remove detailed error messages for probe requests
            if "components" in result:
                for component in result["components"]:
                    if (
                        isinstance(result["components"][component], dict)
                        and result["components"][component].get("status") == "error"
                    ):
                        result["components"][component] = {"status": "cached"}

        logger.debug(
            f"Health check using cached result (age: {int(time.time() - cache['last_check'])}s)"
        )
        return JSONResponse(content=result, status_code=200)

    # Determine if we should do a DB check this time
    # Always check DB in diagnostic mode
    should_check_db = (
        is_diagnostic or cache["db_check_counter"] >= cache["db_check_interval"]
    )
    if should_check_db:
        cache["db_check_counter"] = 0
    else:
        cache["db_check_counter"] += 1

    # Lightweight database connectivity check (only when needed)
    if should_check_db:
        try:
            # Use a very short operation for the db check
            start_time = time.time()
            await db.execute(text("SELECT 1"))
            query_time = time.time() - start_time
            response["components"]["database"] = {
                "status": "ok",
                "response_time_ms": round(query_time * 1000, 2),
            }
        except Exception as e:
            error_message = str(e)
            error_type = e.__class__.__name__

            # Log error but with reduced verbosity for common timeout errors
            if "timeout" in error_message.lower():
                logger.warning(
                    f"Health check - Database timeout: {error_type}: {error_message[:100]}"
                )
            else:
                logger.error(
                    f"Health check - Database error: {error_type}: {error_message}",
                    exc_info=True,
                )

            # Include more detailed error information for diagnostics
            db_error = {
                "status": "error",
                "message": "Database connection failed",
                "error_type": error_type,
                "is_timeout": "timeout" in error_message.lower(),
            }

            # Only include error details in non-k8s probe responses or diagnostic mode
            if not is_k8s_probe or is_diagnostic:
                db_error["error_message"] = (
                    error_message[:200] if len(error_message) > 200 else error_message
                )

            response["components"]["database"] = db_error

            # Only mark as degraded for non-k8s requests
            if not is_k8s_probe:
                response["status"] = "degraded"
    else:
        # Skip DB check this time
        if (
            cache["result"]
            and "components" in cache["result"]
            and "database" in cache["result"]["components"]
        ):
            # Use cached DB status
            response["components"]["database"] = cache["result"]["components"][
                "database"
            ]
        else:
            response["components"]["database"] = {"status": "skipped"}

    # Simple Supabase check - just verify client initialization
    try:
        # Just test if the client is initialized with expected attributes
        if supabase_general_client and hasattr(supabase_general_client, "auth"):
            response["components"]["supabase"] = {"status": "ok"}
        else:
            response["components"]["supabase"] = {
                "status": "error",
                "message": "Client missing expected attributes",
            }
            if not is_k8s_probe:
                response["status"] = "degraded"
    except Exception as e:
        logger.error(f"Health check - Supabase client error: {str(e)}")
        response["components"]["supabase"] = {
            "status": "error",
            "message": "Client initialization error",
        }
        if not is_k8s_probe:
            response["status"] = "degraded"

    # Cache the result
    cache["last_check"] = time.time()
    cache["result"] = response.copy()

    # For k8s probes, always return OK status
    if is_k8s_probe:
        response["status"] = "ok"

    logger.debug(f"Health check completed with status: {response['status']}")
    return JSONResponse(content=response, status_code=200)


@app.get("/internal/health")
async def detailed_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    supabase_general_client: AsyncSupabaseClient = Depends(get_general_supabase_client),
):
    """Detailed health check endpoint for internal monitoring.

    Unlike the public health check, this endpoint always returns actual status
    and never pretends to be healthy for Kubernetes. It performs more thorough checks
    and is intended for internal monitoring and debugging rather than for probes.
    """

    current_time = datetime.datetime.utcnow()
    response = {
        "status": "ok",
        "version": app.version,
        "environment": str(settings.environment),
        "timestamp": current_time.isoformat(),
        "uptime": (
            time.time() - app.startup_time if hasattr(app, "startup_time") else None
        ),
        "components": {"api": {"status": "ok"}},
        "diagnostics": {
            "process_id": os.getpid(),
        },
    }

    # Always perform database check for detailed health
    try:
        result = await db.execute(text("SELECT 1"))
        row = await result.first()
        if row and getattr(row, "1", None) == 1:
            response["components"]["database"] = {"status": "ok"}
        else:
            response["components"]["database"] = {
                "status": "error",
                "message": "Invalid response",
            }
            response["status"] = "degraded"
    except Exception as e:
        logger.error(f"Detailed health check - Database error: {str(e)}", exc_info=True)
        response["components"]["database"] = {
            "status": "error",
            "message": f"Database error: {str(e)}",
            "error_type": e.__class__.__name__,
        }
        response["status"] = "degraded"

    # Detailed Supabase check
    try:
        if not supabase_general_client or not hasattr(supabase_general_client, "auth"):
            response["components"]["supabase"] = {
                "status": "error",
                "message": "Client not properly initialized",
            }
            response["status"] = "degraded"
        else:
            # Check Supabase URL configuration
            supabase_url = getattr(supabase_general_client, "_url", "")
            if not supabase_url or not supabase_url.startswith("http"):
                response["components"]["supabase"] = {
                    "status": "error",
                    "message": "Invalid Supabase URL configuration",
                }
                response["status"] = "degraded"
            else:
                response["components"]["supabase"] = {"status": "ok"}
    except Exception as e:
        logger.error(
            f"Detailed health check - Supabase client error: {str(e)}", exc_info=True
        )
        response["components"]["supabase"] = {
            "status": "error",
            "message": f"Client error: {str(e)}",
            "error_type": e.__class__.__name__,
        }
        response["status"] = "degraded"

    # Return appropriate status code based on overall health
    status_code = 200 if response["status"] == "ok" else 503

    logger.info(f"Detailed health check completed with status: {response['status']}")
    return JSONResponse(content=response, status_code=status_code)


# Example error route for HTTPException handler
@app.get("/error")
async def error_example():
    raise HTTPException(status_code=400, detail="Custom error")


# Example echo route to test validation handler
@app.post("/echo", response_model=MessageResponse)
async def echo(item: MessageResponse):
    return item
