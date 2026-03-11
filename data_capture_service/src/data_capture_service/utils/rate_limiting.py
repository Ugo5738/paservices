"""
Rate limiting configuration for Data Capture Service.
"""

import uuid

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from ..config import settings
from ..utils.logging_config import logger


def _get_limiter_key(request: Request) -> str:
    """
    Determines the client identifier for rate limiting based on the environment.
    """
    if settings.is_testing():
        return str(uuid.uuid4())
    if settings.is_development():
        return "development_client"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_limiter_key,
    default_limits=[getattr(settings, "RATE_LIMIT_GENERAL", "1000/minute")],
    strategy="fixed-window",
)

DATA_CAPTURE_LIMIT = f"{settings.RATE_LIMIT_REQUESTS_PER_MINUTE}/minute"


async def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler for when a rate limit is exceeded."""
    logger.warning(
        "Rate limit exceeded",
        extra={
            "client_host": get_remote_address(request),
            "path": request.url.path,
            "limit": exc.detail,
        },
    )
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else {},
    )


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Configures and adds the rate limiting middleware and exception handler to the FastAPI app.
    """
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if settings.is_testing():
        logger.info(
            "Rate limiting is effectively DISABLED for the testing environment."
        )
    else:
        logger.info(
            "Rate limiting middleware and handler have been successfully configured."
        )
