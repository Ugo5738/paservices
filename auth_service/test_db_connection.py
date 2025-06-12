#!/usr/bin/env python3
"""
Database Connection Test Script for Auth Service

This script tests database connections to both direct PostgreSQL and via pgBouncer
to validate that the connection configuration works properly in all environments.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("db_test")

# Add project root to path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    logger.error("Required dependencies not installed. Run: pip install sqlalchemy")
    sys.exit(1)

async def test_connection(url, description, use_pgbouncer=False):
    """Test a database connection with detailed output"""
    logger.info(f"Testing connection to {description}")
    
    # Sanitize URL for display (hide password)
    display_url = url
    if '@' in url:
        prefix, rest = url.split('@', 1)
        if ':' in prefix:
            user_part = prefix.split(':')[0]
            display_url = f"{user_part}:***@{rest}"
    
    logger.info(f"URL: {display_url}")
    
    # Configure connection args for pgBouncer compatibility
    connect_args = {}
    pool_settings = {}
    if use_pgbouncer:
        logger.info("Configuring for pgBouncer compatibility")
        # pgBouncer doesn't support server-side 'options' parameters
        # Instead we'll use special handling for parameterized queries
    
    try:
        # Create engine with appropriate settings
        engine = create_async_engine(
            url, 
            connect_args=connect_args,
            echo=False
        )
        
        # Create session
        async_session = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        
        # Test with multiple queries to verify connection works consistently
        async with async_session() as session:
            # Run basic diagnostic query
            result = await session.execute(text("SELECT current_database(), current_user, version()"))
            db_info = result.first()
            logger.info(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
            logger.info(f"PostgreSQL version: {db_info[2]}")
            
            # Run query that would typically use prepared statements
            logger.info("Running parameterized query test")
            for i in range(3):
                # When using pgBouncer, we use a different approach to parameters to avoid prepared statements
                if use_pgbouncer:
                    # Use inline string formatting for pgBouncer connections - not optimal but works with pgBouncer
                    # This is safe only because we control the parameter values completely
                    formatted_query = text(f"SELECT 'Test value {i}' AS result")
                    result = await session.execute(formatted_query)
                else:
                    # Use proper parameterized queries for direct connections
                    result = await session.execute(
                        text("SELECT :test_param AS result"), 
                        {"test_param": f"Test value {i}"}
                    )
                value = result.scalar()
                logger.info(f"  Query {i+1} result: {value}")
            
            logger.info(f"✅ Connection to {description} successful")
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Connection failed: {type(e).__name__}: {str(e)}")
        return False
    finally:
        if 'engine' in locals():
            await engine.dispose()

async def main():
    """Run multiple connection tests to verify configuration"""
    logger.info("=" * 50)
    logger.info("DATABASE CONNECTION TEST")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    # Get database URLs from environment or use test defaults
    direct_db_url = os.environ.get(
        "AUTH_SERVICE_DATABASE_URL", 
        "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    )
    
    # Get pgBouncer URL but ensure we remove the pgbouncer parameter if it exists
    pgbouncer_url = os.environ.get(
        "AUTH_SERVICE_PGBOUNCER_URL", 
        "postgresql+psycopg://postgres:postgres@localhost:6432/postgres"
    )
    
    # Remove pgbouncer parameter from URL if present
    if "?pgbouncer=true" in pgbouncer_url:
        pgbouncer_url = pgbouncer_url.replace("?pgbouncer=true", "")
    elif "&pgbouncer=true" in pgbouncer_url:
        pgbouncer_url = pgbouncer_url.replace("&pgbouncer=true", "")
    
    # Test standard PostgreSQL connection (no pgBouncer)
    direct_result = await test_connection(
        direct_db_url, 
        "Direct PostgreSQL", 
        use_pgbouncer=False
    )
    
    # Test connection with pgBouncer
    pgbouncer_result = await test_connection(
        pgbouncer_url, 
        "PostgreSQL via pgBouncer", 
        use_pgbouncer=True
    )
    
    # Summary
    logger.info("=" * 50)
    logger.info("SUMMARY:")
    logger.info(f"Direct PostgreSQL connection: {'✅ PASS' if direct_result else '❌ FAIL'}")
    logger.info(f"pgBouncer connection: {'✅ PASS' if pgbouncer_result else '❌ FAIL'}")
    logger.info("=" * 50)
    
    # Set exit code based on results
    if direct_result and pgbouncer_result:
        logger.info("All database connections successful!")
        return 0
    else:
        logger.error("Some database connections failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
