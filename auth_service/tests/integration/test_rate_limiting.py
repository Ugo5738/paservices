import pytest
import inspect
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch

from auth_service.main import app
from auth_service.rate_limiting import (
    limiter, 
    LOGIN_LIMIT, 
    REGISTRATION_LIMIT, 
    PASSWORD_RESET_LIMIT, 
    TOKEN_LIMIT
)

# Import the route handlers that should have rate limiting
from auth_service.routers.user_auth_routes import login_user, login_magic_link, register_user, request_password_reset
from auth_service.routers.token_routes import get_client_token


def verify_rate_limit_decorator(func, limit_value):
    """Helper function to verify that a function has a rate limit decorator with the expected limit value"""
    # Get the source code of the function
    source = inspect.getsource(func)
    # Check for the decorator pattern in the source code
    decorator_pattern = f"@limiter.limit({limit_value}"
    return decorator_pattern in source


def test_login_rate_limiting():
    """Test that login endpoint is rate limited"""
    # Verify that the login endpoint has rate limiting with the correct limit
    assert verify_rate_limit_decorator(login_user, 'LOGIN_LIMIT')
    
    # Check the actual endpoint to make a basic request
    # No need for async test since we're just checking the decorator application


def test_registration_rate_limiting():
    """Test that registration endpoint is rate limited"""
    # Verify that the registration endpoint has rate limiting with the correct limit
    assert verify_rate_limit_decorator(register_user, 'REGISTRATION_LIMIT')


def test_password_reset_rate_limiting():
    """Test that password reset endpoint is rate limited"""
    # Verify that the password reset endpoint has rate limiting with the correct limit
    assert verify_rate_limit_decorator(request_password_reset, 'PASSWORD_RESET_LIMIT')


def test_token_rate_limiting():
    """Test that token endpoint is rate limited"""
    # Verify that the token endpoint has rate limiting with the correct limit
    assert verify_rate_limit_decorator(get_client_token, 'TOKEN_LIMIT')


def test_magic_link_rate_limiting():
    """Test that magic link login endpoint is rate limited"""
    # Verify that the magic link login endpoint has rate limiting with the correct limit
    assert verify_rate_limit_decorator(login_magic_link, 'LOGIN_LIMIT')


def test_rate_limiting_middleware_setup():
    """Test that rate limiting middleware is properly set up"""
    # Check that the app has a limiter in its state
    assert hasattr(app.state, 'limiter')
    # Check that the app has exception handlers for rate limiting
    assert any('RateLimitExceeded' in str(handler) for handler in app.exception_handlers.keys())
