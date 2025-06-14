#!/usr/bin/env python3
"""
Database Connection Diagnostics Tool

This script provides comprehensive diagnostics for database connections,
including support for pgBouncer compatibility in both development and production
environments.

Usage:
    python check_db.py [--env ENV_NAME] [--verbose]

Options:
    --env ENV_NAME    Environment to check (dev, prod, test) [default: dev]
    --verbose         Show detailed connection information
"""
import argparse
import asyncio
import os
import sys
import time
import urllib.parse
from datetime import datetime

# Determine the project root and add it to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

# Import project settings after adding project root to path
try:
    from src.auth_service.config import settings
    from src.auth_service.logging_config import logger
except ImportError:
    try:
        # Alternate import path
        from auth_service.config import settings
        from auth_service.logging_config import logger
    except ImportError:
        print("Error: Could not import project settings.")
        print("Make sure you're running this script from the project root.")
        sys.exit(1)


def load_env_file(env_name):
    """Load environment variables from the specified .env file"""
    env_file = f".env.{env_name}" if env_name != "default" else ".env"

    if not os.path.exists(env_file):
        print(f"Warning: {env_file} not found.")
        return {}

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip().strip('"').strip("'")

    return env_vars


def parse_connection_url(url):
    """Parse database connection URL and extract pgbouncer parameter if present."""
    if not url:
        return None

    # Handle driver prefix
    driver_prefix = None
    if url.startswith("postgresql+"):
        prefix_end = url.find("://")
        if prefix_end != -1:
            driver_prefix = url[: prefix_end + 3]
            url = url[prefix_end + 3 :]
    elif url.startswith("postgresql://"):
        driver_prefix = "postgresql://"
        url = url[len(driver_prefix) :]

    # Split user/pass from host/port/db
    if "@" in url:
        user_pass, host_port_db = url.split("@", 1)
        if ":" in user_pass:
            username, password = user_pass.split(":", 1)
        else:
            username, password = user_pass, ""
    else:
        username, password = "", ""
        host_port_db = url

    # Handle query parameters
    query_params = {}
    if "?" in host_port_db:
        host_port_db, query_string = host_port_db.split("?", 1)
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value

    # Extract database name
    if "/" in host_port_db:
        host_port, dbname = host_port_db.split("/", 1)
    else:
        host_port, dbname = host_port_db, "postgres"

    # Extract host and port
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        try:
            port = int(port)
        except ValueError:
            port = 5432
    else:
        host, port = host_port, 5432

    # Check if pgbouncer mode is enabled
    pgbouncer_enabled = (
        "pgbouncer" in query_params and query_params["pgbouncer"] == "true"
    )
    pgbouncer_enabled = pgbouncer_enabled or settings.use_pgbouncer

    return {
        "driver_prefix": driver_prefix or "postgresql://",
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "dbname": dbname,
        "pgbouncer_enabled": pgbouncer_enabled,
        "query_params": query_params,
    }


async def check_async_connection(url, env_name="unknown", verbose=False):
    """Test async database connection with detailed diagnostics"""
    print(f"\n{'='*50}")
    print(f"CHECKING ASYNC CONNECTION FOR {env_name.upper()} ENVIRONMENT")
    print(f"{'='*50}")

    conn_params = parse_connection_url(url)
    if not conn_params:
        print("Error: Invalid connection URL")
        return False

    # Mask the password for display
    masked_url = url
    if conn_params["password"]:
        masked_url = masked_url.replace(conn_params["password"], "********")
    print(f"Connection URL: {masked_url}")
    print(f"pgBouncer mode: {conn_params['pgbouncer_enabled']}")

    # Construct a clean connection URL
    clean_url_parts = []
    clean_url_parts.append(conn_params["driver_prefix"])

    if conn_params["username"]:
        auth_part = conn_params["username"]
        if conn_params["password"]:
            auth_part += f":{conn_params['password']}"
        clean_url_parts.append(auth_part + "@")

    clean_url_parts.append(
        f"{conn_params['host']}:{conn_params['port']}/{conn_params['dbname']}"
    )

    # Add query parameters except pgbouncer
    query_params = conn_params["query_params"].copy()
    if "pgbouncer" in query_params:
        del query_params["pgbouncer"]

    if query_params:
        query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
        clean_url_parts.append(f"?{query_string}")

    clean_url = "".join(clean_url_parts)

    # Create connection arguments optimized for pgBouncer if needed
    connect_args = {}
    if conn_params["pgbouncer_enabled"]:
        print("Applying pgBouncer compatibility settings...")
        connect_args["options"] = (
            "-c standard_conforming_strings=on -c client_encoding=utf8 -c plan_cache_mode=force_custom_plan -c statement_timeout=0 -c default_transaction_isolation=read\ committed"
        )

    # Test the connection
    try:
        start_time = time.time()
        engine = create_async_engine(
            clean_url, echo=verbose, future=True, connect_args=connect_args
        )

        print("Attempting to connect...")
        async with engine.begin() as conn:
            # Test a simple query
            result = await conn.execute(
                text(
                    "SELECT 1 as test, current_timestamp, current_database(), current_user"
                )
            )
            row = result.fetchone()
            connect_time = time.time() - start_time

            print(f"\n✅ Connection successful in {connect_time:.3f}s")
            print(f"Database: {row[2]}")
            print(f"User: {row[3]}")
            print(f"Server time: {row[1]}")

            if verbose:
                print("\nChecking database schema:")
                result = await conn.execute(
                    text("SELECT schema_name FROM information_schema.schemata")
                )
                print("Available schemas:")
                schemas = [row[0] for row in result.fetchall()]
                for schema in schemas:
                    print(f"  - {schema}")

                # Check for critical tables
                print("\nChecking critical tables:")
                tables_to_check = ["auth.users", "app_clients", "app_client_roles"]
                for table in tables_to_check:
                    result = await conn.execute(
                        text(
                            f"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
                        ).bindparams(table_name=table.split(".")[-1])
                    )
                    exists = result.scalar()
                    print(f"  - {table}: {'✅ Exists' if exists else '❌ Missing'}")

        return True
    except SQLAlchemyError as e:
        print(f"\n❌ Connection failed: {e.__class__.__name__}: {str(e)}")
        return False
    finally:
        # Clean up
        if "engine" in locals():
            await engine.dispose()


async def check_schemas():
    """Check database schemas and tables for multiple environments"""
    parser = argparse.ArgumentParser(description="Database connection diagnostic tool")
    parser.add_argument(
        "--env",
        choices=["dev", "prod", "test", "all"],
        default="dev",
        help="Environment to check (dev, prod, test, or all)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed connection information"
    )

    args = parser.parse_args()
    verbose = args.verbose

    print(f"Database Connection Diagnostic Tool")
    print(f"Started: {datetime.now().isoformat()}")

    # Track results for final summary
    results = {}

    # Default connection URL from settings
    default_url = settings.database_url

    # Check specific environment or all
    environments = ["dev", "prod", "test"] if args.env == "all" else [args.env]
    for env_name in environments:
        # Load environment-specific variables
        env_vars = load_env_file(env_name)

        # Try to find the database URL for this environment
        db_url = env_vars.get("AUTH_SERVICE_DATABASE_URL", default_url)

        if not db_url:
            print(f"\n❌ No database URL found for {env_name} environment")
            results[env_name] = False
            continue

        # Check the connection
        success = await check_async_connection(db_url, env_name, verbose)
        results[env_name] = success

    # Print summary
    print(f"\n{'='*50}")
    print("SUMMARY:")
    for env, success in results.items():
        print(f"{env.upper()} environment: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"{'='*50}")
    print(f"Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    asyncio.run(check_schemas())
