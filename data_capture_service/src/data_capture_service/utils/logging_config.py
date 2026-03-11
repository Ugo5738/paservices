"""
Logging configuration for the Data Capture Service.
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import Environment, settings

# Configure logger
SERVICE_NAME = (
    settings.PROJECT_NAME if hasattr(settings, "PROJECT_NAME") else "data_capture_service"
)
logger = logging.getLogger(SERVICE_NAME)


class RequestContext:
    """A context manager to store and access the request ID throughout a request's lifecycle."""

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
    """FastAPI middleware to generate a unique request ID for every incoming request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        RequestContext.set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        RequestContext.clear_request_id()
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to log every request and its response automatically."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "Request processed",
                extra={
                    "request": {
                        "method": request.method,
                        "path": request.url.path,
                        "client_host": (
                            request.client.host if request.client else "unknown"
                        ),
                    },
                    "response": {
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                },
            )
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}", exc_info=True)
            raise


class JsonFormatter(logging.Formatter):
    """A custom formatter to output logs in a structured JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.upper(),
            "message": record.getMessage(),
            "service": record.name,
            "request_id": RequestContext.get_request_id(),
            "location": f"{record.module}.{record.funcName}:{record.lineno}",
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_record.update(record.extra)

        return json.dumps(log_record)


def setup_logging(app: Optional[FastAPI] = None) -> None:
    """
    Configures logging for the application.
    """
    log_level = getattr(logging, settings.LOGGING_LEVEL.upper(), logging.INFO)

    formatter = (
        JsonFormatter()
        if settings.is_production()
        else logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    service_logger = logging.getLogger(SERVICE_NAME)
    service_logger.setLevel(log_level)

    # Silence overly verbose libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    if app:
        app.add_middleware(RequestIdMiddleware)

    logger.info(
        f"Logging configured for '{SERVICE_NAME}' at level {settings.LOGGING_LEVEL}"
    )


def configure_logging():
    """Configure logging for non-FastAPI applications like Alembic."""
    setup_logging()
