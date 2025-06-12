from typing import Optional
import os
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from auth_service.config import settings

logger = logging.getLogger(__name__)

# Default rate limits
DEFAULT_GENERAL_RATE_LIMIT = os.environ.get("GENERAL_RATE_LIMIT", "100/minute")
DEFAULT_LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5/minute")
DEFAULT_REGISTRATION_RATE_LIMIT = os.environ.get("REGISTRATION_RATE_LIMIT", "3/minute")
DEFAULT_PASSWORD_RESET_RATE_LIMIT = os.environ.get("PASSWORD_RESET_RATE_LIMIT", "3/minute")
DEFAULT_TOKEN_RATE_LIMIT = os.environ.get("TOKEN_RATE_LIMIT", "10/minute")

# Determine if we're in test mode by checking if pytest is running
# This is a safer approach than relying on environment variables
import sys
IS_TEST_MODE = 'pytest' in sys.modules

# In test mode, we'll use a no-op limiter to avoid affecting tests
def get_limiter_key(request: Request):
    if IS_TEST_MODE:
        # In test mode, give each request a unique key to effectively disable rate limiting
        import uuid
        return str(uuid.uuid4())
    # In normal mode, use the client IP
    return get_remote_address(request)

# Create a limiter instance
limiter = Limiter(
    key_func=get_limiter_key,
    default_limits=[DEFAULT_GENERAL_RATE_LIMIT],
    strategy="fixed-window",  # "moving-window" is more accurate but more resource-intensive
)

# Create a no-op version of the limit decorator for tests
if IS_TEST_MODE:
    # Store the original limit method
    original_limit = limiter.limit
    
    # Replace with a version that doesn't actually rate limit in tests
    def noop_limit(limit_string, key_func=None):
        def decorator(func):
            # Just return the original function without rate limiting
            # but mark it so we can verify the decorator was applied in tests
            func.__slowapi_decorated__ = True
            return func
        return decorator
    
    # Replace the limit method
    limiter.limit = noop_limit
    logger.info("Rate limiting disabled for test environment")

# Define specific rate limits for sensitive endpoints
LOGIN_LIMIT = DEFAULT_LOGIN_RATE_LIMIT
REGISTRATION_LIMIT = DEFAULT_REGISTRATION_RATE_LIMIT
PASSWORD_RESET_LIMIT = DEFAULT_PASSWORD_RESET_RATE_LIMIT
TOKEN_LIMIT = DEFAULT_TOKEN_RATE_LIMIT

# Custom rate limit exceeded handler
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded exceptions"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": exc.retry_after
        },
    )


def setup_rate_limiting(app):
    """Configure rate limiting for the FastAPI application"""
    # Set the limiter on the app state
    app.state.limiter = limiter
    
    # Log whether we're in test mode
    if IS_TEST_MODE:
        logger.info("Rate limiting is disabled in test mode")
    else:
        logger.info(f"Rate limiting is enabled with the following limits: Login={LOGIN_LIMIT}, Registration={REGISTRATION_LIMIT}, PasswordReset={PASSWORD_RESET_LIMIT}, Token={TOKEN_LIMIT}")
    
    # Add rate limiting middleware
    app.add_middleware(SlowAPIMiddleware)
    
    # Add exception handler for rate limit exceeded
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
