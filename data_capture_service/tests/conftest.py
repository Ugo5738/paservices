"""
Shared test fixtures for the Data Capture Service test suite.
"""

import os

import pytest

# Set environment variables for testing BEFORE importing application code
os.environ.setdefault("DATA_CAPTURE_SERVICE_ENVIRONMENT", "testing")
os.environ.setdefault(
    "DATA_CAPTURE_SERVICE_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/data_capture_test",
)
os.environ.setdefault("DATA_CAPTURE_SERVICE_M2M_CLIENT_ID", "test-client-id")
os.environ.setdefault("DATA_CAPTURE_SERVICE_M2M_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("DATA_CAPTURE_SERVICE_M2M_JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("DATA_CAPTURE_SERVICE_LOGGING_LEVEL", "DEBUG")
