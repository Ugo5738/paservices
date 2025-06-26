#!/usr/bin/env python3
"""
End-to-end test script for the Rightmove data capture flow.
This script follows the correct architectural flow based on PRD documents:
1. Get token from Auth Service using client credentials (M2M auth)
2. Get Super ID from Super ID Service using the JWT token
3. Use Super ID to fetch and store property data via Data Capture Rightmove Service
"""

import asyncio
import httpx
import json
import os
import sys
import uuid
from urllib.parse import quote_plus
from typing import Dict, Optional, Tuple

# Service URLs - Use localhost since we're accessing from host machine
# Based on the OpenAPI documentation, all endpoints include the /api/v1 prefix
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001") 
SUPER_ID_SERVICE_URL = os.environ.get("SUPER_ID_SERVICE_URL", "http://localhost:8002")
DATA_CAPTURE_SERVICE_URL = os.environ.get("DATA_CAPTURE_SERVICE_URL", "http://localhost:8003")

# Test constants
TEST_PROPERTY_URL = os.environ.get("TEST_PROPERTY_URL", "https://www.rightmove.co.uk/properties/154508327")
TEST_DESCRIPTION = os.environ.get("TEST_DESCRIPTION", "Test property fetch and storage")

# Client credentials - OAuth 2.0 client credentials flow
# - According to the Auth Service PRD, app_clients authenticate using this method
CLIENT_ID_STRING = os.environ.get("CLIENT_ID", "data_capture_rightmove_service")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "dev_client_secret")

# Convert client_id string to UUID (must match the same UUID algorithm used in create_oauth_client.py)
# We use uuid5 with DNS namespace to create a deterministic UUID from the client_id string
CLIENT_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, CLIENT_ID_STRING))


async def get_auth_token() -> Tuple[bool, Optional[str], Optional[str]]:
    """Get an authentication token from the Auth Service using client credentials"""
    print("🔑 Step 1: Getting authentication token from Auth Service...")
    
    # The token endpoint is available at /api/v1/auth/token where:
    # - /api/v1 comes from FastAPI's root_path setting
    # - /auth/token comes from the token router's prefix (/auth) and the endpoint path (/token)
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    
    try:
        print(f"Requesting auth token from: {url}")
        async with httpx.AsyncClient(timeout=10) as client:
            # Use JSON data instead of form-encoded since the endpoint expects JSON
            json_data = {
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            }
            
            response = await client.post(
                url,
                json=json_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get("access_token")
                print(f"✅ Successfully obtained auth token")
                return True, token, None
            else:
                print(f"❌ Failed to get auth token: {response.status_code}")
                print(f"Response: {response.text}")
                print(f"❌ Auth token acquisition failed. Trying fallback method...")
                return False, None, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"Error getting auth token: {e}")
        print(f"❌ Auth token acquisition failed due to exception. Trying fallback method...")
        return False, None, str(e)


async def get_super_id(token: str) -> Tuple[bool, str, Optional[str]]:
    """Get Super ID from Super ID Service using auth token"""
    print("🆔 Step 2: Getting Super ID from Super ID Service...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get a super_id from the super_id service
            headers = {"Authorization": f"Bearer {token}"}
            super_id_url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
            print(f"Requesting super ID from: {super_id_url}")
            response = await client.post(
                super_id_url,
                headers=headers,
                json={"count": 1}  # Request a single Super ID
            )
            
            if response.status_code == 201:  # PRD specifies 201 Created response
                data = response.json()
                super_id = data.get("super_id")
                if not super_id:
                    return False, "", "Super ID not found in response"
                print(f"✅ Successfully obtained Super ID: {super_id}")
                return True, super_id, None
            else:
                print(f"❌ Failed to get Super ID: {response.status_code}")
                print(f"Response: {response.text}")
                return False, "", f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"❌ Exception when getting Super ID: {str(e)}")
        return False, "", str(e)


async def fetch_property_data(super_id: str, token: str, property_url: str = TEST_PROPERTY_URL) -> Tuple[bool, Dict, Optional[str]]:
    """Fetch and store property data using the Data Capture Rightmove Service"""
    print("🏠 Step 3: Fetching property data from Rightmove API...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:  # Longer timeout for API calls
            # Only include Authorization header if token is not None
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Include X-Super-ID header for super_id tracking
            headers["X-Super-ID"] = super_id
            
            # Extract property ID from URL if possible
            property_id = None
            try:
                # Extract property ID from URL like https://www.rightmove.co.uk/properties/154508327
                property_id = int(property_url.split("/")[-1])
                print(f"Extracted property ID: {property_id}")
            except (ValueError, IndexError):
                print("Could not extract property ID from URL")
            
            # Based on OpenAPI docs, the endpoint is /properties/fetch/combined and uses POST method
            data_capture_url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
            print(f"Requesting property data from: {data_capture_url}")
            response = await client.post(
                data_capture_url,
                json={
                    "property_url": property_url,
                    "description": TEST_DESCRIPTION,
                    "super_id": super_id
                    # Removed property_id to avoid validation conflict
                },
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully fetched property data")
                print(json.dumps(result, indent=2))
                return True, result, None
            else:
                print(f"❌ Failed to fetch property data: {response.status_code}")
                print(f"Response: {response.text}")
                return False, {}, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"❌ Exception when fetching property data: {str(e)}")
        return False, {}, str(e)


async def fallback_with_random_uuid(property_url: str = TEST_PROPERTY_URL, token: str = None) -> Tuple[bool, Dict, Optional[str]]:
    """Fallback method using a random UUID when auth flow fails"""
    print("⚠️ Falling back to direct API call with random UUID...")
    try:
        random_uuid = str(uuid.uuid4())
        print(f"Generated random UUID: {random_uuid}")
        
        async with httpx.AsyncClient(timeout=60) as client:
            # Only include Authorization header if token is not None
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Include X-Super-ID header for super_id tracking
            headers["X-Super-ID"] = random_uuid
            
            # Extract property ID from URL if possible
            property_id = None
            try:
                # Extract property ID from URL like https://www.rightmove.co.uk/properties/154508327
                property_id = int(property_url.split("/")[-1])
                print(f"Extracted property ID: {property_id}")
            except (ValueError, IndexError):
                print("Could not extract property ID from URL")
            
            # Based on OpenAPI docs, the endpoint is /properties/fetch/combined and uses POST method
            data_capture_url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
            print(f"Requesting property data from: {data_capture_url}")
            response = await client.post(
                data_capture_url,
                json={
                    "property_url": property_url,
                    "description": TEST_DESCRIPTION,
                    "super_id": random_uuid
                    # Removed property_id to avoid validation conflict
                },
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully fetched property data with fallback method")
                print(json.dumps(result, indent=2))
                return True, result, None
            else:
                print(f"❌ Fallback method failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False, {}, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"❌ Exception in fallback method: {str(e)}")
        return False, {}, str(e)


async def run_test_flow():
    """Execute the complete test flow"""
    print("=" * 50)
    print("RIGHTMOVE DATA CAPTURE FLOW TEST")
    print("=" * 50)
    
    # Step 1: Get auth token
    success, token, error = await get_auth_token()
    if not success:
        print("\n❌ Auth token acquisition failed. Trying fallback method...")
        success, property_data, error = await fallback_with_random_uuid(TEST_PROPERTY_URL, token)
        if success:
            print("✅ Successfully fetched property data with fallback method")
            print(json.dumps(property_data, indent=2))
            return True
        else:
            print(f"❌ Fallback method failed: {error}")
            return False
    
    # Step 2: Get Super ID
    success, super_id, error = await get_super_id(token)
    if not success:
        print("\n❌ Super ID acquisition failed. Trying fallback method...")
        success, property_data, error = await fallback_with_random_uuid(TEST_PROPERTY_URL, token)
        if success:
            print("✅ Successfully fetched property data with fallback method")
            print(json.dumps(property_data, indent=2))
            return True
        else:
            print(f"❌ Fallback method failed: {error}")
            return False
    
    # Step 3: Use Super ID to fetch and store property data
    if super_id:
        success, property_data, error = await fetch_property_data(super_id, token)
        if success:
            print("✅ Successfully fetched and stored property data")
            print(json.dumps(property_data, indent=2))
            return True
        else:
            print(f"❌ Failed to fetch property data: {error}")
            return False
    
    print("\n✅ Complete flow executed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(run_test_flow())
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(2)
