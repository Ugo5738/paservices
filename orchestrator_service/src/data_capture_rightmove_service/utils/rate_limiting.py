"""
Rate limiting configuration for Data Capture Rightmove Service.
"""

from typing import Callable, Optional

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.utils.logging_config import logger


def get_key_function() -> Callable:
    """
    Return the appropriate key function for rate limiting.

    In production, this would use the client IP or API key.
    In development, it uses a fixed value for easier testing.

    Returns:
        A function that extracts the rate limiting key from the request
    """
    if settings.is_development() or settings.is_testing():
        # Use a constant key in development for easier testing
        logger.debug("Using development rate limiting key function")
        return lambda _: "development"
    else:
        # Use client IP in production
        logger.debug("Using production rate limiting key function based on client IP")
        return get_remote_address


# Initialize the rate limiter with the appropriate key function
limiter = Limiter(key_func=get_key_function())


def configure_rate_limiter(request: Request, response: Response) -> None:
    """
    Configure rate limiter for the current request.

    Args:
        request: FastAPI request object
        response: FastAPI response object
    """
    # Add rate limiting headers to the response
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS_PER_MINUTE)

    # Additional rate limiting configuration can be added here
    if hasattr(request.state, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(
            request.state.rate_limit_remaining
        )

    if hasattr(request.state, "rate_limit_reset"):
        response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)

    # Log rate limiting information in debug mode
    logger.debug(
        f"Rate limiting applied to {request.method} {request.url.path} "
        f"from {get_remote_address(request)}"
    )
