"""
Helper functions for testing.
Provides utility functions for seeding test data and other common operations.
"""

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth_service.logging_config import logger


async def seed_test_user(
    db_session: AsyncSession,
    user_id: str = None,
    email: str = None,
    username: str = None,
) -> str:
    """
    Create a test user record directly in the auth.users table to satisfy foreign key constraints.
    Returns the created user's ID.

    Args:
        db_session: SQLAlchemy AsyncSession object
        user_id: Optional UUID string for the user ID (generated if not provided)
        email: Optional email address (generated if not provided)
        username: Optional username (generated if not provided)

    Returns:
        str: The UUID of the created user
    """
    if user_id is None:
        user_id = str(uuid.uuid4())

    if email is None:
        email = f"test_{user_id}@example.com"

    if username is None:
        username = f"testuser_{user_id[:8]}"

    # Create user metadata with the username
    user_meta_data = json.dumps(
        {"username": username, "first_name": "Test", "last_name": "User"}
    )
    app_meta_data = json.dumps({})

    # Insert the user record into the auth.users table using raw SQL
    # Using f-string interpolation for safe value insertion with explicit type casting
    insert_sql = text(
        f"""
        INSERT INTO auth.users (
            id, 
            raw_user_meta_data,
            raw_app_meta_data,
            is_anonymous,
            created_at, 
            updated_at,
            role,
            aud
        )
        VALUES (
            '{user_id}'::uuid,
            '{email}',
            '{user_meta_data}'::jsonb,
            '{app_meta_data}'::jsonb,
            false,
            NOW(),
            NOW(),
            'authenticated',
            'authenticated'
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    try:
        await db_session.execute(insert_sql)
        await db_session.flush()
        logger.info(
            f"Successfully seeded test user in auth.users: {user_id} | {username}"
        )
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        await db_session.rollback()
        raise

    return user_id
