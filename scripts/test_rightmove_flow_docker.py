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
from typing import Dict, Optional, Tuple, Any

# Service URLs - Using Docker service names for inter-container communication
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth_service:8000") 
SUPER_ID_SERVICE_URL = os.environ.get("SUPER_ID_SERVICE_URL", "http://super_id_service:8000")
DATA_CAPTURE_SERVICE_URL = os.environ.get("DATA_CAPTURE_SERVICE_URL", "http://data_capture_rightmove_service:8000")

# Test constants
TEST_PROPERTY_URL = os.environ.get("TEST_PROPERTY_URL", "https://www.rightmove.co.uk/properties/154508327")
TEST_DESCRIPTION = os.environ.get("TEST_DESCRIPTION", "Test property fetch and storage")

# Client credentials - OAuth 2.0 client credentials flow
CLIENT_ID_STRING = os.environ.get("CLIENT_ID", "data_capture_rightmove_service")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "dev_client_secret")

# Convert client_id string to UUID (must match the same UUID algorithm used in create_oauth_client.py)
CLIENT_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, CLIENT_ID_STRING))


async def get_auth_token() -> Tuple[bool, Optional[str], Optional[str]]:
    """Get an authentication token from the Auth Service using client credentials"""
    print("🔑 Step 1: Getting authentication token from Auth Service...")
    
    # The token endpoint is available at /api/v1/auth/token
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    
    try:
        print(f"Requesting auth token from: {url}")
        async with httpx.AsyncClient(timeout=10) as client:
            # Make a POST request with form data in the body
            response = await client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            # Extract the access token from the response
            if "access_token" in token_data:
                token = token_data["access_token"]
                print("✅ Successfully obtained an auth token")
                return True, token, None
            else:
                print(f"❌ Failed to obtain an auth token: {token_data}")
                return False, None, f"No access_token in response: {token_data}"
                
    except httpx.HTTPError as e:
        print(f"Error getting auth token: {str(e)}")
        return False, None, str(e)


async def get_super_id(auth_token: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Get a Super ID from the Super ID Service using the auth token"""
    print("\n🪪 Step 2: Getting Super ID from Super ID Service...")
    
    # The Super ID endpoint is available at /api/v1/super-id
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super-id"
    
    try:
        print(f"Requesting Super ID from: {url}")
        async with httpx.AsyncClient(timeout=10) as client:
            # Make a POST request with the JWT token in the Authorization header
            response = await client.post(
                url,
                json={"description": f"Test Super ID for Rightmove flow: {TEST_DESCRIPTION}"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            response.raise_for_status()
            super_id_data = response.json()
            
            # Extract the Super ID from the response
            if "id" in super_id_data:
                super_id = super_id_data["id"]
                print(f"✅ Successfully obtained a Super ID: {super_id}")
                return True, super_id, None
            else:
                print(f"❌ Failed to obtain a Super ID: {super_id_data}")
                return False, None, f"No id in response: {super_id_data}"
                
    except httpx.HTTPError as e:
        print(f"Error getting Super ID: {str(e)}")
        return False, None, str(e)


def extract_property_id_from_url(url: str) -> Optional[str]:
    """Extract a Rightmove property ID from a URL"""
    try:
        # Simple extraction - expecting a URL like https://www.rightmove.co.uk/properties/123456789
        parts = url.split("/")
        return parts[-1].split("#")[0].split("?")[0]  # Get last part, remove any fragment or query
    except Exception as e:
        print(f"Error extracting property ID from URL: {str(e)}")
        return None


async def fetch_property_data(auth_token: str, super_id: str, property_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Fetch property data from the Data Capture Rightmove Service"""
    print("\n🏠 Step 3: Fetching property data from the Data Capture Service...")
    
    # Extract the property ID from the URL
    property_id = extract_property_id_from_url(property_url)
    if not property_id:
        return False, None, "Could not extract property ID from URL"
        
    print(f"Extracted property ID: {property_id}")
    
    # The property fetch endpoint is available at /api/v1/properties/fetch/combined
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
    
    try:
        print(f"Requesting property data from: {url}")
        async with httpx.AsyncClient(timeout=20) as client:  # Longer timeout for property data
            # Make a POST request with the property details and the JWT token
            response = await client.post(
                url,
                json={
                    "property_url": property_url,
                    "super_id": super_id,
                    "description": TEST_DESCRIPTION
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            response.raise_for_status()
            property_data = response.json()
            print("✅ Successfully fetched property data")
            
            # Print a structured summary of the results
            print("\n📋 Property Data Summary:")
            print(f"Property ID: {property_data.get('property_id')}")
            print(f"Property URL: {property_data.get('property_url')}")
            print("\nAPI Endpoint Results:")
            
            for result in property_data.get('results', []):
                endpoint = result.get('api_endpoint')
                stored = result.get('stored')
                message = result.get('message')
                print(f"  - {endpoint}: {'✅ Stored' if stored else '❌ Not stored'}")
                if message:
                    print(f"    Message: {message}")
                    
            return True, property_data, None
                
    except httpx.HTTPError as e:
        print(f"Error fetching property data: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False, None, str(e)


async def fallback_test() -> None:
    """Fallback method if auth fails - using direct API calls with a generated UUID"""
    try:
        print("\n⚠️ Falling back to direct API call with random UUID...")
        # Generate a random UUID to use as the Super ID
        random_super_id = str(uuid.uuid4())
        print(f"Generated random UUID: {random_super_id}")
        
        # Extract the property ID from the URL
        property_id = extract_property_id_from_url(TEST_PROPERTY_URL)
        if not property_id:
            print("❌ Could not extract property ID from URL")
            return
            
        print(f"Extracted property ID: {property_id}")
        
        # The property fetch endpoint is available at /api/v1/properties/fetch/combined
        url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
        
        print(f"Requesting property data from: {url}")
        async with httpx.AsyncClient(timeout=20) as client:  # Longer timeout for property data
            # Make a POST request with the property details but no auth token
            response = await client.post(
                url,
                json={
                    "property_url": TEST_PROPERTY_URL,
                    "super_id": random_super_id,
                    "description": TEST_DESCRIPTION
                }
            )
            
            response.raise_for_status()
            property_data = response.json()
            
            # Print a structured summary of the results
            print("\n📋 Property Data Summary (Fallback):")
            print(f"Property ID: {property_data.get('property_id')}")
            print(f"Property URL: {property_data.get('property_url')}")
            print("\nAPI Endpoint Results:")
            
            for result in property_data.get('results', []):
                endpoint = result.get('api_endpoint')
                stored = result.get('stored')
                message = result.get('message')
                print(f"  - {endpoint}: {'✅ Stored' if stored else '❌ Not stored'}")
                if message:
                    print(f"    Message: {message}")
                
    except Exception as e:
        print(f"❌ Exception in fallback method: {str(e)}")
        print(f"❌ Fallback method failed: {str(e)}")


async def main():
    """Main function to run the full test flow"""
    print("=" * 50)
    print("RIGHTMOVE DATA CAPTURE FLOW TEST")
    print("=" * 50)
    
    # Step 1: Get an auth token from Auth Service
    success, token, error = await get_auth_token()
    if not success:
        print(f"❌ Auth token acquisition failed due to exception. Trying fallback method...")
        print(f"\n❌ Auth token acquisition failed. Trying fallback method...")
        await fallback_test()
        return
        
    # Step 2: Get a Super ID from Super ID Service
    success, super_id, error = await get_super_id(token)
    if not success:
        print(f"❌ Super ID acquisition failed: {error}")
        print("Trying fallback method...")
        await fallback_test()
        return
        
    # Step 3: Use the Super ID to fetch and store property data
    success, property_data, error = await fetch_property_data(token, super_id, TEST_PROPERTY_URL)
    if not success:
        print(f"❌ Property data fetch failed: {error}")
    
    print("\n✨ Test completed! ✨")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
