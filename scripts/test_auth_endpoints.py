#!/usr/bin/env python3
"""
Test script to identify the correct auth service endpoint path
"""

import asyncio
import httpx
import sys
from typing import Dict, List, Tuple

# Base URL for the auth service
BASE_URL = "http://localhost:8001"

# List of path combinations to try
PATHS_TO_TEST = [
    "/auth/token",
    "/api/v1/auth/token",
    "/api/v1/api/v1/auth/token",
    "/token",
    "/api/v1/token",
    # Try some other combinations
    "/v1/auth/token",
    "/auth/v1/token",
]

# Test client credentials
CLIENT_CREDS = {
    "grant_type": "client_credentials",
    "client_id": "test_client",
    "client_secret": "test_secret",
}

async def test_path(path: str) -> Tuple[str, int, str]:
    """Test a specific path with both GET and POST requests"""
    url = f"{BASE_URL}{path}"
    print(f"Testing URL: {url}")
    
    try:
        # Try GET request first to see if the endpoint exists
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            status = response.status_code
            text = response.text if status != 200 else "OK"
            print(f"  GET: {status} - {text[:50]}...")
            
            if status != 404:  # If not 404, try a POST with client credentials
                response = await client.post(
                    url,
                    json=CLIENT_CREDS,
                    headers={"Content-Type": "application/json"}
                )
                status = response.status_code
                text = response.text
                print(f"  POST: {status} - {text[:50]}...")
                
            return path, status, text
    except Exception as e:
        print(f"  Error: {str(e)}")
        return path, 0, str(e)

async def main():
    results = []
    for path in PATHS_TO_TEST:
        result = await test_path(path)
        results.append(result)
        await asyncio.sleep(0.5)  # Small delay between requests
    
    print("\nSummary:")
    print("-" * 60)
    for path, status, _ in results:
        print(f"{path:25} : {status}")

if __name__ == "__main__":
    asyncio.run(main())
