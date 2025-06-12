import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import Request
from auth_service.logging_config import RequestContext

# Get dedicated security audit logger
logger = logging.getLogger("auth_service.security")


def _sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive information from data before logging.
    """
    # Create a copy to avoid modifying the original data
    sanitized = data.copy()
    
    # List of keys that contain sensitive information
    sensitive_keys = [
        "password", "new_password", "old_password", "token", "access_token", 
        "refresh_token", "api_key", "key", "secret", "authorization"
    ]
    
    # Recursively sanitize nested dictionaries
    for key, value in list(sanitized.items()):
        # Check if this is a sensitive key
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        # Recursively sanitize nested dictionaries
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_data(value)
    
    return sanitized


def log_security_event(
    event_type: str, 
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    status: str = "success",
    detail: Optional[str] = None,
) -> None:
    """
    Log a security-related event with structured data.
    
    Args:
        event_type: Type of security event (e.g., "login", "password_reset")
        user_id: UUID of the user associated with the event
        ip_address: IP address of the user
        additional_data: Any additional relevant data
        request: FastAPI request object
        status: Outcome status ("success", "failure", "attempt")
        detail: Optional detailed message
    """
    # Create the security event log structure
    security_event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "status": status,
    }
    
    # Add user ID if provided
    if user_id:
        security_event["user_id"] = str(user_id)
    
    # Add request ID if available
    request_id = RequestContext.get_request_id()
    if request_id:
        security_event["request_id"] = request_id
    
    # Add IP address, either from parameter or request
    if ip_address:
        security_event["ip_address"] = ip_address
    elif request and request.client:
        security_event["ip_address"] = request.client.host
    
    # Add request information if available
    if request:
        security_event["request"] = {
            "method": request.method,
            "path": request.url.path,
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    
    # Add additional data if provided, ensuring sensitive information is redacted
    if additional_data:
        security_event["data"] = _sanitize_data(additional_data)
    
    # Add detailed message if provided
    if detail:
        security_event["detail"] = detail
    
    # Log the security event
    log_message = f"Security event: {event_type} - {status}"
    logger.info(log_message, extra={"security_event": security_event})


# Convenience functions for common security events
def log_login_attempt(request: Request, email: str, status: str = "attempt", detail: Optional[str] = None):
    """
    Log a login attempt.
    """
    log_security_event(
        event_type="login_attempt",
        ip_address=request.client.host if request and request.client else None,
        additional_data={"email": email},
        request=request,
        status=status,
        detail=detail
    )


def log_login_success(request: Request, user_id: UUID, email: str):
    """
    Log a successful login.
    """
    log_security_event(
        event_type="login_success",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        additional_data={"email": email},
        request=request,
        status="success"
    )


def log_login_failure(request: Request, email: str, reason: str):
    """
    Log a failed login attempt.
    """
    log_security_event(
        event_type="login_failure",
        ip_address=request.client.host if request and request.client else None,
        additional_data={"email": email},
        request=request,
        status="failure",
        detail=reason
    )


def log_password_reset_request(request: Request, email: str):
    """
    Log a password reset request.
    """
    log_security_event(
        event_type="password_reset_request",
        ip_address=request.client.host if request and request.client else None,
        additional_data={"email": email},
        request=request,
        status="attempt"
    )


def log_password_change(request: Request, user_id: UUID, status: str = "success", detail: Optional[str] = None):
    """
    Log a password change event.
    """
    log_security_event(
        event_type="password_change",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        request=request,
        status=status,
        detail=detail
    )


def log_admin_action(request: Request, user_id: UUID, action: str, target_id: Optional[str] = None, additional_data: Optional[Dict[str, Any]] = None):
    """
    Log an administrative action.
    """
    data = additional_data or {}
    data["action"] = action
    if target_id:
        data["target_id"] = target_id
        
    log_security_event(
        event_type="admin_action",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        additional_data=data,
        request=request,
        status="success"
    )


def log_oauth_event(request: Request, provider: str, user_id: Optional[UUID] = None, status: str = "attempt", detail: Optional[str] = None):
    """
    Log an OAuth authentication event.
    """
    log_security_event(
        event_type="oauth_authentication",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        additional_data={"provider": provider},
        request=request,
        status=status,
        detail=detail
    )
