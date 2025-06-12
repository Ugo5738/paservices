#!/usr/bin/env python3
"""
Script to apply migrations to the super_id_service test database.
"""

import os
import sys
import logging
import asyncio
import subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
import urllib.parse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST", "supabase_db_paservices")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_NAME = os.environ.get("DB_NAME", "super_id_test_db")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
ALEMBIC_DIR = os.environ.get("ALEMBIC_DIR", str(Path(__file__).parent.parent / "migrations"))

# Tables expected to exist after migration
EXPECTED_TABLES = {
    "public.generated_super_ids",  # Main table for storing generated super IDs
    "alembic_version"             # Alembic version tracking table
}

async def verify_database_connection():
    """Verify connection to the database."""
    conn_string = f"host={DB_HOST} port={DB_PORT} dbname=postgres user={DB_USER} password={DB_PASSWORD}"
    try:
        conn = await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row)
        await conn.close()
        logger.info("✅ Successfully connected to database")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        return False

async def create_database_if_not_exists():
    """Create the test database if it doesn't exist."""
    conn_string = f"host={DB_HOST} port={DB_PORT} dbname=postgres user={DB_USER} password={DB_PASSWORD}"
    try:
        conn = await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row)
        await conn.set_autocommit(True)
        
        async with conn.cursor() as cursor:
            await cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
            result = await cursor.fetchone()
            
            if not result:
                logger.info(f"Creating database {DB_NAME}...")
                await cursor.execute(f"CREATE DATABASE {DB_NAME}")
                logger.info(f"✅ Database {DB_NAME} created successfully")
            else:
                logger.info(f"Database {DB_NAME} already exists")
        
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create database: {e}")
        return False

async def verify_tables():
    """Verify that all expected tables exist."""
    conn_string = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    try:
        conn = await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row)
        
        # Get all tables from all schemas
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT table_schema || '.' || table_name AS full_table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            """)
            tables = set(row['full_table_name'] for row in await cursor.fetchall())
        
        await conn.close()
        
        # Check if all expected tables exist
        missing_tables = EXPECTED_TABLES - tables
        if missing_tables:
            logger.error(f"❌ Missing tables: {missing_tables}")
            logger.info(f"Found tables: {tables}")
            return False
        else:
            logger.info(f"✅ All expected tables exist: {EXPECTED_TABLES}")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to verify tables: {e}")
        return False

async def run_alembic_migrations():
    """Run Alembic migrations."""
    try:
        logger.info(f"Running Alembic migrations from {ALEMBIC_DIR}...")
        env = os.environ.copy()
        
        # Make sure alembic uses the right database URL
        env["DATABASE_URL"] = DATABASE_URL
        
        # Run Alembic migrations
        cmd = ["alembic", "-c", f"{ALEMBIC_DIR}/alembic.ini", "upgrade", "head"]
        process = subprocess.Popen(
            cmd, 
            env=env, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ Alembic migrations applied successfully")
            logger.info(f"Migration output: {stdout}")
            return True
        else:
            logger.error(f"❌ Alembic migrations failed with code {process.returncode}")
            logger.error(f"Error output: {stderr}")
            logger.error(f"Standard output: {stdout}")
            
            # Fall back to direct SQL migrations
            logger.warning("Falling back to direct SQL table creation...")
            return await create_tables_with_direct_sql()
    except Exception as e:
        logger.error(f"❌ Failed to run Alembic migrations: {e}")
        # Fall back to direct SQL migrations
        logger.warning("Falling back to direct SQL table creation...")
        return await create_tables_with_direct_sql()

async def create_tables_with_direct_sql():
    """Create tables directly with SQL if Alembic migrations fail."""
    logger.info("Creating tables with direct SQL statements")
    conn_string = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    
    try:
        conn = await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row)
        
        # Create tables with SQL statements based on our actual models
        table_creation_sqls = [
            """
            CREATE TABLE IF NOT EXISTS public.generated_super_ids (
                id BIGSERIAL PRIMARY KEY,
                super_id UUID NOT NULL UNIQUE,
                generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                requested_by_client_id VARCHAR(255),
                metadata JSONB
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) PRIMARY KEY
            )
            """
        ]
        
        async with conn.cursor() as cursor:
            for sql in table_creation_sqls:
                try:
                    await cursor.execute(sql)
                    await conn.commit()
                    logger.info(f"✅ Executed SQL: {sql.strip().split('(')[0]}")
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"❌ Failed to execute SQL: {e}")
                    logger.error(f"SQL statement: {sql}")
        
        # Verify tables after creation
        existing_tables = set()
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT table_schema || '.' || table_name AS full_table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            """)
            existing_tables = set(row['full_table_name'] for row in await cursor.fetchall())
        
        logger.info(f"Tables after direct SQL creation: {existing_tables}")
        missing_tables = EXPECTED_TABLES - existing_tables
        if missing_tables:
            logger.error(f"❌ Still missing tables after direct SQL: {missing_tables}")
        
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create tables with direct SQL: {e}")
        return False

async def main():
    """Main function to run migrations."""
    logger.info("Starting super_id_service test database migrations")
    
    # Verify database connection
    if not await verify_database_connection():
        logger.error("Unable to connect to database. Exiting.")
        return False
    
    # Create database if needed
    if not await create_database_if_not_exists():
        logger.error("Failed to create database. Exiting.")
        return False
    
    # Run Alembic migrations
    if not await run_alembic_migrations():
        logger.error("Failed to apply migrations. Exiting.")
        return False
    
    # Verify expected tables
    if not await verify_tables():
        logger.warning("Not all expected tables exist after migration.")
    
    logger.info("✅ super_id_service test database migration completed")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
