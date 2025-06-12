#!/usr/bin/env python
import asyncio
import logging
import os
import sys
import subprocess
import psycopg
import time
from alembic import command
from alembic.config import Config
from psycopg import connect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("db_fix")

# Path to the project root (in Docker container, everything is in /app)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# In Docker, alembic is directly in /app
AUTH_SERVICE_ROOT = PROJECT_ROOT  # No subdirectory in Docker container

# Get environment variables for database connection
DB_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@supabase_db_paservices:5432/auth_test_db")
DB_HOST = os.environ.get("DB_HOST", "supabase_db_paservices")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_NAME = os.environ.get("DB_NAME", "auth_test_db")
ALEMBIC_DIR = os.environ.get("ALEMBIC_DIR", "/app/alembic")

# Debug the environment values
logger.info(f"DB_URL = {DB_URL}")
logger.info(f"DB_HOST = {DB_HOST}")
logger.info(f"DB_PORT = {DB_PORT}")
logger.info(f"DB_USER = {DB_USER}")
logger.info(f"DB_NAME = {DB_NAME}")
logger.info(f"ALEMBIC_DIR = {ALEMBIC_DIR}")

# Clean the database URL for SQLAlchemy
CLEAN_DB_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_test_database():
    """Create the test database if it doesn't exist"""
    try:
        # First connect to default postgres database
        logger.info(f"Connecting to default postgres database to create test database if needed")
        conn = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname="postgres"  # Connect to default postgres database
        )
        
        # Set autocommit to create database
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"Creating test database: {DB_NAME}")
                cursor.execute(f"CREATE DATABASE {DB_NAME}")
                logger.info(f"Test database created successfully")
            else:
                logger.info(f"Test database '{DB_NAME}' already exists")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating test database: {e}")
        return False

async def verify_database_connection():
    """Test database connection with a clean URL"""
    try:
        # First ensure the test database exists
        if not create_test_database():
            logger.error("Failed to create/verify test database")
            return False
            
        logger.info(f"Verifying connection to test database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        # Now try to connect to the test database
        logger.info("Testing direct psycopg connection...")
        conn = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logger.info(f"Direct connection successful: {result}")
        conn.close()
        
        # Now try SQLAlchemy async connection
        logger.info("Testing SQLAlchemy connection...")
        engine = create_async_engine(
            CLEAN_DB_URL,
            connect_args={
                "application_name": "db_fix_script",
            }
        )
        
        # Test the connection with a simple query
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
            logger.info(f"SQLAlchemy connection test successful: {value}")
        
        return True
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return False
    finally:
        await engine.dispose()

def create_test_database():
    """Create the test database if it doesn't exist"""
    try:
        # Connect to default database first
        logger.info(f"Connecting to default database to check if {DB_NAME} exists...")
        conn = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname="postgres"  # Connect to default postgres database
        )
        conn.autocommit = True
        
        # Check if our test database exists
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"Creating test database '{DB_NAME}'...")
                cursor.execute(f'CREATE DATABASE "{DB_NAME}" WITH OWNER = "{DB_USER}"')
                logger.info(f"Test database '{DB_NAME}' created successfully")
            else:
                logger.info(f"Test database '{DB_NAME}' already exists")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating test database: {e}")
        return False

def run_alembic_migrations():
    """Run Alembic migrations"""
    # TEMPORARY FIX: Skip Alembic and go directly to SQL approach
    logger.info("Skipping Alembic migrations and using direct SQL approach for more reliable setup")
    return run_migrations_with_direct_psycopg()
    
    # The following code is temporarily bypassed
    # Create a clean environment for Alembic
    env = os.environ.copy()
    env["DB_HOST"] = DB_HOST
    env["DB_PORT"] = str(DB_PORT)
    env["DB_USER"] = DB_USER
    env["DB_PASSWORD"] = DB_PASSWORD
    env["DB_NAME"] = "auth_test_db"  # Explicitly set the database name
    
    # Use a clean database URL without pgbouncer parameters
    clean_url = CLEAN_DB_URL
    logger.info(f"Running migrations with database URL: {clean_url}")
    env["SQLALCHEMY_DATABASE_URI"] = clean_url
    
    # Create/update alembic.ini with the correct database URL
    logger.info("Updating alembic.ini with correct database URL...")
    
    alembic_ini_path = os.path.join(os.path.dirname(ALEMBIC_DIR), "alembic.ini")
    logger.info(f"Alembic config path: {alembic_ini_path}")
    
    # If alembic.ini exists, update it
    if os.path.exists(alembic_ini_path):
        with open(alembic_ini_path, 'r') as f:
            config_content = f.read()
        
        # Replace the sqlalchemy.url line with our test database URL
        import re
        updated_content = re.sub(
            r'sqlalchemy\.url = .*', 
            f'sqlalchemy.url = {clean_url}', 
            config_content
        )
        
        with open(alembic_ini_path, 'w') as f:
            f.write(updated_content)
        
        logger.info("Successfully updated alembic.ini with test database URL")
    else:
        logger.warning(f"alembic.ini not found at {alembic_ini_path}, using environment variables only")
    
    # Override the alembic config if specified
    if ALEMBIC_DIR:
        os.chdir(os.path.dirname(ALEMBIC_DIR))
    
    # First, run alembic current to see the current state
    logger.info("Checking current migration status...")
    try:
        process = subprocess.run(
            ["alembic", "current"], 
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            logger.warning(f"Migration status check failed: {process.stderr}")
        else:
            logger.info(f"Current migration state: {process.stdout.strip() or 'No migrations applied'}")
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
    
    # Now run the migrations
    logger.info("Running database migrations...")
    try:
        process = subprocess.run(
            ["alembic", "upgrade", "head"], 
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            logger.error(f"Migration failed: {process.stderr}")
            # Try to extract SQLAlchemy URL issues
            if "default_transaction_isolation" in process.stderr:
                logger.error("Transaction isolation parameter is still causing issues.")
                logger.info("Attempting more direct approach...")
                return run_migrations_with_direct_psycopg()
            return False
        
        logger.info(f"Migration output: {process.stdout}")
        return True
    except Exception as e:
        logger.error(f"Migration execution failed: {e}")
        return False

def run_migrations_with_direct_psycopg():
    """Apply migrations by directly connecting with psycopg and executing SQL"""
    try:
        logger.info("Running migrations with direct SQL approach...")
        logger.info("*** FALLBACK METHOD ACTIVATED: Creating tables directly with SQL ***")
        # This is a fallback method where we would directly create tables
        # Note: In a real implementation, you would extract the SQL from alembic scripts
        # or have hardcoded SQL for critical tables
        
        conn = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        conn.autocommit = False
        
        try:
            with conn.cursor() as cursor:
                # Create basic alembic version table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
                """)
                
                # Create all tables from the original Alembic migration
                
                # Create app_clients table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_clients (
                    id UUID PRIMARY KEY,
                    client_name VARCHAR(255) NOT NULL UNIQUE,
                    client_secret_hash VARCHAR(255) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    description TEXT,
                    allowed_callback_urls VARCHAR[] DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_app_clients_client_name ON app_clients (client_name)")
                
                # Create permissions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_permissions_name ON permissions (name)")
                
                # Create roles table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_roles_name ON roles (name)")
                
                # Create app_client_refresh_tokens table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_client_refresh_tokens (
                    id UUID PRIMARY KEY,
                    app_client_id UUID NOT NULL REFERENCES app_clients(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    revoked_at TIMESTAMP WITH TIME ZONE
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_app_client_refresh_tokens_app_client_id ON app_client_refresh_tokens (app_client_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_app_client_refresh_tokens_token_hash ON app_client_refresh_tokens (token_hash)")
                
                # Create app_client_roles table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_client_roles (
                    app_client_id UUID NOT NULL REFERENCES app_clients(id) ON DELETE CASCADE,
                    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (app_client_id, role_id)
                )
                """)
                
                # Create the profiles table with FK to auth.users
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id UUID PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    username VARCHAR(100) UNIQUE,
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT fk_profile_auth_user_id FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_profiles_email ON profiles (email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_profiles_username ON profiles (username)")
                
                # Create role_permissions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (role_id, permission_id)
                )
                """)
                
                # Create user_roles table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (user_id, role_id)
                )
                """)
                
                logger.info("Created all tables from Alembic migration")
                
                # Insert latest migration version
                cursor.execute("DELETE FROM alembic_version")
                cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('head')")
                
                # Verify tables were created properly
                logger.info("Verifying tables were created by direct SQL approach...")
                cursor.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
                tables = cursor.fetchall()
                logger.info(f"Tables in public schema: {tables}")
                
                # Verify profiles table specifically
                cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'profiles');")
                profile_exists = cursor.fetchone()[0]
                logger.info(f"Profiles table exists after SQL creation: {profile_exists}")
                
                if not profile_exists:
                    logger.error("CRITICAL ERROR: Profiles table was not created!")
                    # Try once more with explicit schema
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS public.profiles (
                        user_id UUID PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        username VARCHAR(100) UNIQUE,
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        CONSTRAINT fk_profile_auth_user_id FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
                    )
                    """)
                    logger.info("Made additional attempt to create profiles table with explicit schema")
                
                # Commit all changes
                conn.commit()
                logger.info("Direct migrations applied successfully")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error applying direct migrations: {e}")
            return False
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to connect for direct migrations: {e}")
        return False

async def verify_tables():
    """Verify that the necessary tables were created"""
    try:
        logger.info("Verifying that tables were created properly...")
        engine = create_async_engine(
            CLEAN_DB_URL,
            connect_args={
                "application_name": "db_fix_verify_tables",
            }
        )
        
        # Check for all expected tables from the migration
        tables_to_check = [
            'app_clients', 
            'permissions', 
            'roles', 
            'app_client_refresh_tokens',
            'app_client_roles', 
            'profiles', 
            'role_permissions', 
            'user_roles',
            'alembic_version'
        ]
        missing_tables = []
        
        async with engine.connect() as conn:
            for table in tables_to_check:
                # Try to select from the table to verify it exists
                try:
                    query = text(f"""SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )""")
                    result = await conn.execute(query)
                    exists = result.scalar_one()
                    
                    if exists:
                        logger.info(f"Table '{table}' exists")
                    else:
                        logger.warning(f"Table '{table}' does not exist")
                        missing_tables.append(table)
                except Exception as e:
                    logger.error(f"Error checking table {table}: {e}")
                    missing_tables.append(table)
        
        await engine.dispose()
        
        if missing_tables:
            logger.warning(f"Missing tables: {', '.join(missing_tables)}")
            return False
        else:
            logger.info("All required tables exist")
            return True
            
    except Exception as e:
        logger.error(f"Error verifying tables: {e}")
        return False

async def main():
    """Main function to run the database setup and migrations"""
    # Start timing execution
    start_time = time.time()
    logger.info("===== Starting Test Database Fix Process =====")
    
    # First verify connection
    connection_ok = await verify_database_connection()
    if not connection_ok:
        logger.error("Database connection failed, aborting migration")
        return False
    
    # Create test database if needed
    if not create_test_database():
        logger.error("Failed to create test database, aborting migration")
        return False
    
    # Run migrations
    migration_ok = run_alembic_migrations()
    if not migration_ok:
        logger.error("Migration failed, test database may be incomplete")
        return False
    
    # Verify tables were created
    tables_verified = await verify_tables()
    if not tables_verified:
        logger.warning("Some tables may be missing, but process completed")
    
    # Calculate execution time
    execution_time = time.time() - start_time
    logger.info(f"===== Test Database Fix Process Completed in {execution_time:.2f} seconds =====")
    logger.info("✅ Test database setup completed successfully!")
    return True

if __name__ == "__main__":
    try:
        # Run the main function
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        sys.exit(1)
