import json
import logging
import sys
import time
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
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        RequestContext.set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        RequestContext.clear_request_id()
        return response


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            # --- FIX: Use uppercase attribute ---
            "environment": str(settings.ENVIRONMENT.value),
        }
        if request_id := RequestContext.get_request_id():
            log_record["request_id"] = request_id
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and record.extra:
            log_record.update(record.extra)
        return json.dumps(log_record)


def setup_logging(app: FastAPI) -> None:
    """Configure logging for the application"""
    # --- FIX: Use uppercase attribute ---
    log_level = getattr(logging, settings.LOGGING_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- FIX: Use uppercase attribute ---
    if settings.ENVIRONMENT == Environment.PRODUCTION:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)

    # Configure specific loggers if needed
    logging.getLogger("auth_service").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    app.add_middleware(RequestIdMiddleware)

    logger.info(
        # --- FIX: Use uppercase attribute ---
        f"Logging configured with level {settings.LOGGING_LEVEL} "
        f"and {'JSON' if settings.ENVIRONMENT == Environment.PRODUCTION else 'plain text'} format"
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request and response information"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health", "/internal/health"]:
            return await call_next(request)

        start_time = time.time()
        request_id = RequestContext.get_request_id()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "Request processed",
                extra={
                    "request": {
                        "method": request.method,
                        "path": request.url.path,
                        "client_host": request.client.host,
                        "request_id": request_id,
                    },
                    "response": {
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                },
            )
            return response
        except Exception as e:
            logger.error(
                f"Request failed: {e}", exc_info=True, extra={"request_id": request_id}
            )
            raise
