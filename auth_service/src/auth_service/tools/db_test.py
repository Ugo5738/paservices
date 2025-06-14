#!/usr/bin/env python
"""
Database connection diagnostic tool for Supabase Cloud.

Tests connection to the Supabase database with detailed diagnostics.
This script can run both as a standalone diagnostic tool and as part of pytest test suite.
"""
import argparse
import asyncio
import os
import socket

# Import project settings
import sys
import time
from datetime import datetime

import httpx
import psycopg
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Fix import paths - add project root to Python path
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../..")
)
sys.path.append(project_root)

# Now import from the proper location based on project structure
from auth_service.config import settings
from auth_service.db import AsyncSessionLocal, get_db

# Check if pytest is available
try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


def parse_connection_url(url):
    """Parse database connection URL and extract pgbouncer parameter if present."""
    import urllib.parse

    # Remove the driver prefix for parsing
    clean_url = url.replace("postgresql+psycopg://", "")
    # Split user/pass from host/port/db
    if "@" in clean_url:
        user_pass, host_port_db = clean_url.split("@", 1)
        username, password = (
            user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
        )
    else:
        username, password = "", ""
        host_port_db = clean_url

    # Handle query parameters if present
    if "?" in host_port_db:
        host_port_db, query_string = host_port_db.split("?", 1)
        query_params = urllib.parse.parse_qs(query_string)
    else:
        query_params = {}

    # Extract database name
    if "/" in host_port_db:
        host_port, dbname = host_port_db.split("/", 1)
    else:
        host_port, dbname = host_port_db, "postgres"

    # Extract host and port
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432

    # Check if pgbouncer mode is enabled
    pgbouncer_enabled = (
        "pgbouncer" in query_params and query_params["pgbouncer"][0] == "true"
    )

    return {
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "dbname": dbname,
        "pgbouncer_enabled": pgbouncer_enabled,
        "query_params": query_params,
    }


async def test_direct_connection():
    """Test direct connection to Supabase database without SQLAlchemy."""
    print(f"\n{'='*20} DIRECT CONNECTION TEST {'='*20}")

    # Parse connection string to get components
    conn_params = parse_connection_url(settings.database_url)
    username = conn_params["username"]
    password = conn_params["password"]
    host = conn_params["host"]
    port = conn_params["port"]
    dbname = conn_params["dbname"]

    start_time = time.time()
    print(f"Connecting to {host}:{port} as {username}...")

    # Test DNS resolution
    try:
        print(f"Resolving DNS for {host}...")
        dns_start = time.time()
        ip_addresses = socket.getaddrinfo(
            host, port, socket.AF_INET, socket.SOCK_STREAM
        )
        dns_time = time.time() - dns_start
        print(f"DNS resolution successful in {dns_time*1000:.2f}ms")
        print(f"IP addresses: {', '.join(addr[4][0] for addr in ip_addresses)}")
    except socket.gaierror as e:
        print(f"DNS resolution failed: {e}")
        return False

    # Connection test
    try:
        conn_start = time.time()
        # Use psycopg async connection
        # Build connection options that work with both psycopg2 and psycopg3
        conn_kwargs = {
            "user": username,
            "password": password,
            "host": host,
            "port": port,
            "dbname": dbname,
            "connect_timeout": 10,  # 10 second connection timeout
        }

        # Add options for disabling prepared statements in a way that works with pgBouncer
        if conn_params["pgbouncer_enabled"]:
            conn_kwargs["options"] = (
                r"-c standard_conforming_strings=on -c client_encoding=utf8 -c plan_cache_mode=force_custom_plan -c statement_timeout=0 -c default_transaction_isolation=read\ committed"
            )
            print("pgBouncer mode detected - disabling prepared statements")

        conn = await psycopg.AsyncConnection.connect(**conn_kwargs)
        conn_time = time.time() - conn_start
        print(f"Connection established in {conn_time*1000:.2f}ms")

        # Create an async cursor
        async with conn.cursor() as cur:
            # Test simple query
            query_start = time.time()
            await cur.execute("SELECT version()")
            version = await cur.fetchone()
            query_time = time.time() - query_start
            print(f"Query completed in {query_time*1000:.2f}ms")
            print(f"Database version: {version[0]}")

            # Test connection pool settings
            await cur.execute("SHOW ALL")
            params = await cur.fetchall()
            print("\nServer parameters:")
            for row in params:
                param_name, param_value = row[0], row[1]
                if any(
                    kw in param_name
                    for kw in ["conn", "pool", "timeout", "statement", "idle"]
                ):
                    print(f"  {param_name} = {param_value}")

        await conn.close()
        return True
    except Exception as e:
        print(f"Direct connection failed: {e.__class__.__name__}: {str(e)}")
        return False


async def test_sqlalchemy_connection():
    """Test SQLAlchemy connection with the application's configuration."""
    print(f"\n{'='*20} SQLALCHEMY CONNECTION TEST {'='*20}")

    try:
        # Parse connection URL and handle pgBouncer mode
        conn_params = parse_connection_url(settings.database_url)

        # Import necessary SQLAlchemy components
        # Build clean connection URL without pgbouncer parameter
        import urllib.parse

        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        base_url = f"postgresql+psycopg://{conn_params['username']}:{conn_params['password']}@{conn_params['host']}:{conn_params['port']}/{conn_params['dbname']}"

        # Set up connect_args for pgBouncer compatibility if needed
        connect_args = {}
        if conn_params["pgbouncer_enabled"]:
            print("PgBouncer mode detected, configuring connection appropriately")
            connect_args.update(
                {"prepared_statement_cache_size": 0, "statement_cache_size": 0}
            )

        print(f"Creating engine with pgbouncer={conn_params['pgbouncer_enabled']}")
        test_engine = create_async_engine(
            base_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

        # Create session
        print("Creating SQLAlchemy session...")
        TestAsyncSessionLocal = sessionmaker(
            test_engine, expire_on_commit=False, class_=AsyncSession
        )
        session = TestAsyncSessionLocal()

        print("Testing connection...")
        start = time.time()
        result = await session.execute(text("SELECT 1"))
        basic_time = time.time() - start
        print(f"Basic connection test completed in {basic_time*1000:.2f}ms")

        print("Testing complex query...")
        start = time.time()
        result = await session.execute(
            text(
                """
            SELECT 
                pg_database.datname as "Database",
                pg_size_pretty(pg_database_size(pg_database.datname)) as "Size",
                pg_stat_database.numbackends as "Connections",
                pg_stat_database.xact_commit as "Commits",
                pg_stat_database.xact_rollback as "Rollbacks"
            FROM pg_database
            LEFT JOIN pg_stat_database ON pg_database.oid = pg_stat_database.datid
            WHERE pg_database.datistemplate = false
            ORDER BY pg_database_size(pg_database.datname) DESC;
            """
            )
        )
        complex_time = time.time() - start
        print(f"Complex query completed in {complex_time*1000:.2f}ms")

        print("\nDatabase statistics:")
        rows = result.mappings().all()
        for row in rows:
            print(
                f"  {row['Database']} ({row['Size']}) - {row['Connections']} connections"
            )

        # Test multiple queries to check connection pool behavior
        print("\nTesting connection pool with multiple queries...")
        times = []
        for i in range(5):
            start = time.time()
            await session.execute(text("SELECT pg_sleep(0.1), current_timestamp"))
            query_time = time.time() - start
            times.append(query_time)
            print(f"Query {i+1}: {query_time*1000:.2f}ms")

        avg_time = sum(times) / len(times)
        print(f"Average query time: {avg_time*1000:.2f}ms")

        await session.close()
        return True
    except SQLAlchemyError as e:
        print(f"SQLAlchemy connection failed: {e.__class__.__name__}: {str(e)}")
        return False


async def test_supabase_api():
    """Test Supabase API connectivity."""
    print(f"\n{'='*20} SUPABASE API TEST {'='*20}")

    supabase_url = (
        settings.supabase_url
        if hasattr(settings, "supabase_url")
        else os.environ.get("AUTH_SERVICE_SUPABASE_URL")
    )
    if not supabase_url:
        print("Supabase URL not found in settings or environment variables")
        return False

    try:
        print(f"Testing connection to Supabase API at {supabase_url}...")
        start = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{supabase_url}/rest/v1/", timeout=10.0)
        api_time = time.time() - start

        print(f"API connection test completed in {api_time*1000:.2f}ms")
        print(f"Status code: {response.status_code}")
        print(f"Headers: {response.headers}")

        return (
            response.status_code < 500
        )  # Consider it successful if not a server error
    except Exception as e:
        print(f"Supabase API connection failed: {e.__class__.__name__}: {str(e)}")
        return False


async def run_all_tests():
    """Run all connection tests and report results."""
    print(f"\n{'='*50}")
    print(f"DATABASE CONNECTION DIAGNOSTICS")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"{'='*50}")

    print("\nConnection string:")
    # Mask password in connection string for security
    masked_url = settings.database_url
    if "@" in masked_url and ":" in masked_url.split("@")[0]:
        user_part, rest = masked_url.split("@", 1)
        user, password = user_part.split(":", 1)
        masked_url = f"{user}:{'*' * 8}@{rest}"
    print(f"  {masked_url}")

    # Run all tests
    direct_success = await test_direct_connection()
    sqlalchemy_success = await test_sqlalchemy_connection()
    supabase_api_success = await test_supabase_api()

    # Print summary
    print(f"\n{'='*50}")
    print("SUMMARY:")
    print(f"Direct Connection:     {'✅ PASS' if direct_success else '❌ FAIL'}")
    print(f"SQLAlchemy Connection: {'✅ PASS' if sqlalchemy_success else '❌ FAIL'}")
    print(f"Supabase API:          {'✅ PASS' if supabase_api_success else '❌ FAIL'}")
    print(f"{'='*50}")

    if direct_success and sqlalchemy_success:
        print("\n✅ Database connection is working correctly!")
        print("The application should be able to connect to the database.")
    else:
        print("\n⚠️ Some database connection tests failed!")
        print("Review the errors above to troubleshoot connectivity issues.")

    print(f"\nCompleted at: {datetime.now().isoformat()}")


# Add pytest markers if we're running in pytest
if HAS_PYTEST:
    # Apply the pytest.mark.asyncio decorator to all test functions
    test_direct_connection = pytest.mark.asyncio(test_direct_connection)
    test_sqlalchemy_connection = pytest.mark.asyncio(test_sqlalchemy_connection)
    test_supabase_api = pytest.mark.asyncio(test_supabase_api)
    run_all_tests = pytest.mark.asyncio(run_all_tests)


# When imported as a module during pytest collection, don't run the tests automatically
# When run as a standalone script, execute the tests
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test database connection")
    args = parser.parse_args()

    asyncio.run(run_all_tests())
