"""
Main conftest file that imports and re-exports all fixtures from modular files.
This approach improves maintainability by organizing fixtures into logical modules.
"""

import asyncio
import os

from dotenv import load_dotenv

# Explicitly load the test environment variables before importing any app modules
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env.test")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)
else:
    print(f"Warning: .env.test file not found at {dotenv_path}")

# Now reload the config to ensure it picks up test settings
from importlib import reload

from auth_service import config

reload(config)

# Make seed_test_user available as a fixture as well for convenience
import pytest

# Import and re-export fixtures from modular files
# This keeps this file clean while allowing tests to import fixtures normally
from tests.fixtures.client import client
from tests.fixtures.db import db_session, event_loop, setup_test_database
from tests.fixtures.helpers import seed_test_user
from tests.fixtures.mocks import (
    MockCrud,
    MockSupabaseResponse,
    mock_supabase_client,
)

# The imports above automatically register the fixtures with pytest
# so they will be available to all test modules without explicit imports


@pytest.fixture
def test_user_helper():
    """Return the seed_test_user helper function directly as a fixture."""
    return seed_test_user
