#!/usr/bin/env python
"""
Simple Supabase Database Connection Tester

This script directly tests the connection to your Supabase Cloud database
without relying on the auth_service module structure.
"""
import os
import sys
import time
import asyncio
import socket
from datetime import datetime

# Import required packages - install if needed with: pip install asyncpg httpx
try:
    import asyncpg
    import httpx
except ImportError:
    print("Required packages not found. Please install them with:")
    print("pip install asyncpg httpx")
    sys.exit(1)

# Default database URL - can be overridden with environment variable
# Use pgBouncer port (6543) and enable pgbouncer mode
DEFAULT_DB_URL = "postgresql+asyncpg://postgres.ndindbknmovckjouvcvh:Cutesome57381@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
DEFAULT_SUPABASE_URL = "https://ndindbknmovckjouvcvh.supabase.co"

# Get connection details from environment or use defaults
DB_URL = os.environ.get("AUTH_SERVICE_DATABASE_URL", DEFAULT_DB_URL)
SUPABASE_URL = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)


async def test_direct_connection():
    """Test direct connection to Supabase database with pgBouncer settings."""
    print(f"\n{'='*20} DIRECT DATABASE CONNECTION TEST {'='*20}")
    
    # Extract connection parameters from URL
    # Format: postgresql+asyncpg://username:password@host:port/dbname?pgbouncer=true
    base_url = DB_URL.replace('postgresql+asyncpg://', '')
    
    # Check if pgbouncer=true is in the URL
    is_pgbouncer = 'pgbouncer=true' in base_url
    conn_str = base_url.split('?')[0]  # Remove query params for parsing
    
    # Split into user:pass@host:port/dbname
    user_pass, host_port_db = conn_str.split('@', 1)
    username, password = user_pass.split(':', 1)
    
    # Split into host:port and dbname
    if '/' in host_port_db:
        host_port, dbname = host_port_db.split('/', 1)
    else:
        host_port, dbname = host_port_db, 'postgres'
    
    # Split into host and port
    if ':' in host_port:
        host, port = host_port.split(':', 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    
    print(f"Database Host: {host}")
    print(f"Database Port: {port}")
    print(f"Database Name: {dbname}")
    print(f"Username: {username}")
    print(f"Using pgBouncer mode: {is_pgbouncer}")
    
    # Test DNS resolution
    try:
        print(f"\nResolving DNS for {host}...")
        dns_start = time.time()
        ip_addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        dns_time = time.time() - dns_start
        print(f"✅ DNS resolution successful ({dns_time*1000:.2f}ms)")
        print(f"  IP addresses: {', '.join(addr[4][0] for addr in ip_addresses)}")
    except socket.gaierror as e:
        print(f"❌ DNS resolution failed: {e}")
        return False
    
    # Test database connection
    try:
        print(f"\nConnecting to database...")
        conn_start = time.time()
        conn = await asyncpg.connect(
            user=username,
            password=password,
            host=host,
            port=port,
            database=dbname,
            timeout=15.0,  # 15 second connection timeout
            command_timeout=10.0,  # 10 second command timeout
            server_settings={
                # pgBouncer requires READ COMMITTED isolation level
                "application_name": "auth_service_diagnostic",
                "default_transaction_isolation": "read committed",
            } if is_pgbouncer else {}
        )
        conn_time = time.time() - conn_start
        print(f"✅ Connection established ({conn_time*1000:.2f}ms)")
        
        # Test simple query
        print(f"\nExecuting test query...")
        query_start = time.time()
        version = await conn.fetchval('SELECT version()')
        query_time = time.time() - query_start
        print(f"✅ Query successful ({query_time*1000:.2f}ms)")
        print(f"  Database version: {version}")
        
        # Test connection stability (fewer queries to avoid rate limits)
        print(f"\nTesting connection stability with 2 sequential queries...")
        times = []
        for i in range(2):  # Reduced from 5 to 2 to prevent rate limit issues
            start = time.time()
            await conn.execute('SELECT 1')
            query_time = time.time() - start
            times.append(query_time)
            print(f"  Query {i+1}: {query_time*1000:.2f}ms")
            await asyncio.sleep(0.5)  # Add small delay between queries
            
        avg = sum(times) / len(times)
        print(f"  Average query time: {avg*1000:.2f}ms")
        
        # Only get server parameters if not using pgBouncer
        # pgBouncer doesn't support some of these parameters
        if not is_pgbouncer:
            print(f"\nChecking server parameters...")
            params = await conn.fetchrow('''
                SELECT 
                    current_setting('max_connections') as max_connections,
                    current_setting('idle_in_transaction_session_timeout') as idle_timeout,
                    current_setting('statement_timeout') as statement_timeout
            ''')
            
            print(f"  Max connections: {params['max_connections']}")
            print(f"  Idle timeout: {params['idle_timeout']} ms")
            print(f"  Statement timeout: {params['statement_timeout']} ms")
        else:
            print("\nSkipping server parameter check (not supported in pgBouncer mode)")
        
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e.__class__.__name__}: {str(e)}")
        return False


async def test_supabase_api():
    """Test connection to Supabase API."""
    print(f"\n{'='*20} SUPABASE API TEST {'='*20}")
    
    try:
        print(f"Connecting to Supabase API at {SUPABASE_URL}...")
        start = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SUPABASE_URL}/rest/v1/", timeout=5.0)
        api_time = time.time() - start
        
        print(f"✅ API request completed ({api_time*1000:.2f}ms)")
        print(f"  Status code: {response.status_code}")
        
        if 200 <= response.status_code < 500:
            print(f"✅ Supabase API is reachable")
            return True
        else:
            print(f"⚠️ Supabase API returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Supabase API request failed: {e.__class__.__name__}: {str(e)}")
        return False


async def run_all_tests():
    """Run all database connection tests."""
    print(f"{'='*60}")
    print(f"DATABASE CONNECTION DIAGNOSTIC TOOL")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    print(f"\nTesting connection to: {DB_URL.replace('postgresql+asyncpg://', 'postgresql://')}")
    
    db_success = await test_direct_connection()
    api_success = await test_supabase_api()
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"Database Connection: {'✅ PASS' if db_success else '❌ FAIL'}")
    print(f"Supabase API:        {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"{'='*60}")
    
    if db_success and api_success:
        print("\n✅ All tests passed! Your connection to Supabase is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Review the errors above for troubleshooting.")
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")
    return db_success and api_success


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        sys.exit(130)  # Standard exit code for SIGINT
