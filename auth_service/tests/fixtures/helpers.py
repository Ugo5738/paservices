"""
Helper functions for testing.
Provides utility functions for seeding test data and other common operations.
"""
import uuid
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_test_user(db_session: AsyncSession, user_id: str = None, email: str = None, username: str = None) -> str:
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
    user_meta_data = json.dumps({"username": username})
    app_meta_data = json.dumps({})
    
    # Ensure we have the auth.users table
    try:
        # Insert the user record into the auth.users table using raw SQL
        # Using f-string interpolation for safe value insertion with explicit type casting
        await db_session.execute(
            text(f"""
            INSERT INTO auth.users (
                id, 
                raw_user_meta_data,
                raw_app_meta_data,
                is_anonymous,
                created_at, 
                updated_at,
                role
            )
            VALUES (
                '{user_id}'::uuid,
                '{user_meta_data}'::jsonb,
                '{app_meta_data}'::jsonb,
                false,
                NOW(),
                NOW(),
                'authenticated'
            )
            ON CONFLICT (id) DO NOTHING
            """)
        )
        
        # Commit the transaction
        await db_session.commit()
        print(f"Created test user in auth.users: {user_id} | {username}")
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        await db_session.rollback()
        raise
    
    return user_id
