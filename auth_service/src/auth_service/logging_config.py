import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from auth_service.config import Environment, settings

# Configure logger
logger = logging.getLogger("auth_service")


# Request ID context for correlating log entries from the same request
class RequestContext:
    """Thread-local storage for request context such as request ID"""

    _request_id: Optional[str] = None

    @classmethod
    def get_request_id(cls) -> Optional[str]:
        return cls._request_id

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        cls._request_id = request_id

    @classmethod
    def clear_request_id(cls) -> None:
        cls._request_id = None


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to each request"""

    async def dispatch(self, request: Request, call_next):
        # Generate a unique request ID if not provided in headers
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store request ID in context
        RequestContext.set_request_id(request_id)

        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Clear request ID after request is processed
        RequestContext.clear_request_id()

        return response


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        # Base log record attributes
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "environment": str(settings.environment.value),
        }

        # Add request ID if available
        request_id = RequestContext.get_request_id()
        if request_id:
            log_record["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add any extra attributes passed to the logger
        if hasattr(record, "extra") and record.extra:
            log_record.update(record.extra)

        return json.dumps(log_record)


def setup_logging(app: FastAPI) -> None:
    """Configure logging for the application"""
    # Determine log level from settings
    log_level = getattr(logging, settings.logging_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use JSON formatter in production, plain text in development
    if settings.environment == Environment.PRODUCTION:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure auth_service logger
    app_logger = logging.getLogger("auth_service")
    app_logger.setLevel(log_level)

    # Add request ID middleware
    app.add_middleware(RequestIdMiddleware)

    logger.info(
        f"Logging configured with level {settings.logging_level} "
        f"and {'JSON' if settings.environment == Environment.PRODUCTION else 'plain text'} format"
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request and response information"""

    async def dispatch(self, request: Request, call_next):
        # Don't log health check requests to avoid noise
        if request.url.path == "/health":
            return await call_next(request)

        start_time = datetime.now(timezone.utc)

        # Log request
        request_id = RequestContext.get_request_id() or "unknown"
        logger.info(
            f"Request started",
            extra={
                "request": {
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "client_host": request.client.host if request.client else "unknown",
                    "request_id": request_id,
                }
            },
        )

        try:
            response = await call_next(request)

            # Calculate request duration
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Log response (excluding sensitive endpoints)
            sensitive_paths = ["/auth/token", "/auth/users/login"]
            if not any(request.url.path.startswith(path) for path in sensitive_paths):
                logger.info(
                    f"Request completed",
                    extra={
                        "response": {
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "request_id": request_id,
                        }
                    },
                )
            else:
                # For sensitive endpoints, log less information
                logger.info(
                    f"Sensitive request completed",
                    extra={
                        "response": {
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "request_id": request_id,
                        }
                    },
                )

            return response

        except Exception as e:
            # Log exceptions
            logger.error(
                f"Request failed: {str(e)}",
                exc_info=True,
                extra={
                    "request": {
                        "method": request.method,
                        "path": request.url.path,
                        "request_id": request_id,
                    }
                },
            )
            raise  # Re-raise the exception to be handled by FastAPI
