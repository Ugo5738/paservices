"""
Test configuration for super_id_service.
This sets up the test database, fixtures, and test environment.
"""

import os
import sys
import logging
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_setup")

# Constants
PROJECT_ROOT = Path(os.path.abspath(__file__)).parent.parent
IS_DOCKER = os.path.exists("/app")

# Define test database URL
# Common database parameters
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
TEST_DATABASE_NAME = "super_id_test_db"  # Aligned with our naming convention

if IS_DOCKER:
    # Docker environment
    DB_HOST = os.environ.get("DB_HOST", "supabase_db_paservices")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    TEST_DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DATABASE_NAME}"
else:
    # Local environment
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    TEST_DATABASE_URL = os.environ.get(
        "TEST_DATABASE_URL", 
        f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DATABASE_NAME}"
    )

logger.info(f"Using test database: {TEST_DATABASE_URL.replace(DB_PASSWORD, '****')}")

# Connection and engine configurations
engine = None
test_engine = None

@pytest_asyncio.fixture(scope="session")
async def create_test_database():
    """Create the test database if it doesn't exist."""
    global engine
    
    # Connect to default postgres database
    default_url = TEST_DATABASE_URL.replace(f"/{TEST_DATABASE_NAME}", "/postgres")
    engine = create_async_engine(default_url, poolclass=NullPool)
    
    try:
        # Check if test database exists
        async with engine.connect() as conn:
            result = await conn.execute(
                f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DATABASE_NAME}'"
            )
            exists = result.scalar() is not None
            
            if not exists:
                logger.info(f"Creating test database: {TEST_DATABASE_NAME}")
                # Need to use autocommit mode to create database
                await conn.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
                logger.info(f"Test database created: {TEST_DATABASE_NAME}")
            else:
                logger.info(f"Test database already exists: {TEST_DATABASE_NAME}")
    except Exception as e:
        logger.error(f"Error creating test database: {e}")
        raise
    finally:
        await engine.dispose()
        
    yield

@pytest_asyncio.fixture(scope="session")
async def apply_migrations_to_test_db(create_test_database):
    """Apply migrations to the test database."""
    try:
        import subprocess
        
        # Setup environment variables for the migration script
        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        parsed_url = urlparse(TEST_DATABASE_URL)
        netloc_parts = parsed_url.netloc.split('@')
        
        if len(netloc_parts) > 1:
            host_port = netloc_parts[1].split(':')[0]
            env["DB_HOST"] = host_port
        else:
            env["DB_HOST"] = "supabase_db_paservices"
            
        env["DB_PORT"] = "5432"
        env["DB_USER"] = "postgres"
        env["DB_PASSWORD"] = "postgres"
        env["DB_NAME"] = TEST_DATABASE_NAME
        
        # Determine project root and script locations
        project_root = Path("/app") if IS_DOCKER else PROJECT_ROOT
        
        # Run migrations using Alembic
        logger.info("Running migrations for super_id_service test database...")
        
        # Run the migration script
        script_path = "scripts/super_id_test_migrations.py" if IS_DOCKER else str(project_root / "scripts" / "super_id_test_migrations.py")
        logger.info(f"Running migrations with script: {script_path}")
        
        try:
            result = subprocess.run(
                [sys.executable, script_path], 
                env=env, 
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Migration output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Migration failed: {e.stderr}")
            raise
    
    except Exception as e:
        logger.error(f"Error applying migrations: {e}")
        raise

@pytest_asyncio.fixture(scope="session")
async def db_engine(apply_migrations_to_test_db):
    """Create and return a test database engine."""
    global test_engine
    
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    
    try:
        yield test_engine
    finally:
        await test_engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a new database session for a test."""
    async_session = sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()

# Add any other common fixtures needed for tests below
