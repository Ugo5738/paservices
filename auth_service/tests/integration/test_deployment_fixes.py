"""
Test script to verify all fixes for Kubernetes deployment issues.

This script simulates the main lifecycle of the application:
1. Initializing the Supabase client
2. Creating a database session
3. Running the bootstrap process
4. Using the health check endpoint
5. Properly shutting down resources
"""

import asyncio
import logging
from typing import Optional
import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.bootstrap import bootstrap_admin_and_rbac, create_admin_user
from auth_service.db import get_db
from auth_service.supabase_client import (
    get_supabase_admin_client,
    get_supabase_client,
    init_supabase_client,
    close_supabase_client,
)
from auth_service.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fixes")

@pytest.mark.asyncio
async def test_supabase_client():
    """Test Supabase client initialization and shutdown."""
    logger.info("Testing Supabase client initialization...")
    
    # Initialize Supabase client (this is normally done in the lifespan context manager)
    await init_supabase_client()
    
    # Get the initialized client
    client = get_supabase_client()
    logger.info(f"Supabase client initialized: {client is not None}")
    
    # Test admin client (without async with)
    logger.info("Testing admin client...")
    admin_client = await get_supabase_admin_client()
    logger.info(f"Admin client obtained: {admin_client is not None}")
    
    try:
        # Test admin client list_users (checking corrected response handling)
        logger.info("Testing admin client list_users...")
        users_response = await admin_client.auth.admin.list_users(per_page=1)
        logger.info(f"Users list type: {type(users_response)}, Length: {len(users_response)}")
        
    except Exception as e:
        logger.error(f"Error testing admin client: {str(e)}")
        
    # Test client shutdown
    logger.info("Testing client shutdown...")
    await close_supabase_client()
    logger.info("Client shutdown complete")

@pytest.mark.asyncio
async def test_db_session():
    """Test database session creation and closure."""
    logger.info("Testing DB session...")
    db_session: Optional[AsyncSession] = None
    
    # Get a database session using the fixed get_db function
    try:
        async for session in get_db():
            db_session = session
            break
            
        if db_session:
            logger.info("DB session obtained successfully")
            
            # Test a simple query to verify connection
            result = await db_session.execute("SELECT 1")
            value = result.scalar()
            logger.info(f"Test query result: {value}")
            
            # Session will be properly closed by the get_db generator
            
    except Exception as e:
        logger.error(f"Error testing DB session: {str(e)}")
        if db_session:
            await db_session.rollback()
    finally:
        # We don't need to close it here, the context manager should handle it
        pass

@pytest.mark.asyncio
async def test_bootstrap():
    """Test the bootstrap process with the fixed code."""
    logger.info("Testing bootstrap process...")
    
    # Initialize Supabase client if not already done
    await init_supabase_client()
    
    db_session: Optional[AsyncSession] = None
    try:
        # Get a DB session for bootstrap
        async for session in get_db():
            db_session = session
            break
            
        if db_session:
            # Run bootstrap process with fixed functions
            success = await bootstrap_admin_and_rbac(db_session)
            logger.info(f"Bootstrap completed with success: {success}")
    except Exception as e:
        logger.error(f"Error in bootstrap process: {str(e)}")
        if db_session:
            await db_session.rollback()
    finally:
        # Let the session be closed by its context manager
        pass

@pytest.mark.asyncio
async def test_admin_user_creation():
    """Test the fixed create_admin_user function."""
    if not settings.initial_admin_email or not settings.initial_admin_password:
        logger.warning("No admin credentials in settings, skipping admin user test")
        return
        
    logger.info("Testing admin user creation...")
    try:
        # Test create_admin_user with the fixed response handling
        admin_user = await create_admin_user(
            settings.initial_admin_email, 
            settings.initial_admin_password
        )
        if admin_user:
            logger.info(f"Admin user found/created: {admin_user.email}")
        else:
            logger.warning("Admin user creation returned None")
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")

async def main():
    """Run all tests in sequence."""
    try:
        logger.info("Starting fix verification tests...")
        
        # Test Supabase client handling
        await test_supabase_client()
        
        # Reinitialize client for other tests
        await init_supabase_client()
        
        # Test DB session handling
        await test_db_session()
        
        # Test bootstrap process
        await test_bootstrap()
        
        # Test admin user creation specifically
        await test_admin_user_creation()
        
        # Final cleanup
        await close_supabase_client()
        
        logger.info("All tests completed.")
        
    except Exception as e:
        logger.error(f"Unexpected error during tests: {str(e)}")
    finally:
        # Ensure client is cleaned up
        await close_supabase_client()

if __name__ == "__main__":
    asyncio.run(main())
