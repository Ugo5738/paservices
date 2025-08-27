"""
Rate limiting configuration for Super ID Service.
"""

import uuid

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

# Import the service-specific settings and logger
from ..config import settings
from ..utils.logging_config import logger

# --- Key Function for Identifying Clients ---


def _get_limiter_key(request: Request) -> str:
    """
    Determines the client identifier for rate limiting based on the environment.
    - In TESTING, returns a unique UUID for every request to effectively disable limiting.
    - In DEVELOPMENT, returns a static key to avoid rate-limiting local requests.
    - In PRODUCTION, uses the client's real IP address.
    """
    if settings.is_testing():
        return str(uuid.uuid4())  # Unique key for each request = no rate limiting
    if settings.is_development():
        return "development_client"  # Static key for local development

    # In production, use the client's IP address.
    return get_remote_address(request)


# --- Limiter Instance ---

# Create a single, reusable Limiter instance.
# The default_limits can be set to a general, permissive value.
limiter = Limiter(
    key_func=_get_limiter_key,
    default_limits=[getattr(settings, "RATE_LIMIT_GENERAL", "1000/minute")],
    strategy="fixed-window",  # Efficient strategy for stateless services
)


# --- Rate Limit Constants ---
# These constants read the specific limits from your service's settings file.
# This makes your router code clean and declarative.
LOGIN_LIMIT = getattr(settings, "RATE_LIMIT_LOGIN", "5/minute")
REGISTER_LIMIT = getattr(settings, "RATE_LIMIT_REGISTER", "5/minute")
TOKEN_LIMIT = getattr(settings, "RATE_LIMIT_TOKEN", "20/minute")
PASSWORD_RESET_LIMIT = getattr(settings, "RATE_LIMIT_PASSWORD_RESET", "5/minute")
SUPER_ID_GENERATE_LIMIT = getattr(
    settings, "RATE_LIMIT_SUPER_ID_GENERATE", "100/minute"
)
PROPERTY_FETCH_LIMIT = getattr(settings, "RATE_LIMIT_PROPERTY_FETCH", "30/minute")


# --- Custom Exception Handler ---


async def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """
    Custom handler for when a rate limit is exceeded.
    Returns a clear JSON response with a 429 status code and a Retry-After header.
    """
    # Log the event for security and monitoring purposes
    logger.warning(
        "Rate limit exceeded",
        extra={
            "client_host": get_remote_address(request),
            "path": request.url.path,
            "limit": exc.detail,
        },
    )

    # Provide a consistent and informative error response
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else {},
    )


# --- Setup Function for main.py ---


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Configures and adds the rate limiting middleware and exception handler to the FastAPI app.
    This should be called once from your main.py file.
    """
    # This state object is required by slowapi's middleware
    app.state.limiter = limiter

    # Add the middleware to process requests against the defined limits
    app.add_middleware(SlowAPIMiddleware)

    # Add the custom handler to manage responses when a limit is exceeded
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if settings.is_testing():
        logger.info(
            "Rate limiting is effectively DISABLED for the testing environment."
        )
    else:
        logger.info(
            "Rate limiting middleware and handler have been successfully configured."
        )
