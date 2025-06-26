#!/usr/bin/env python3
"""
Debug script to investigate Rightmove API responses and property ID issues.
"""

import os
import asyncio
import json
from urllib.parse import urlparse, parse_qs

import httpx

# Use the same environment variables as the service
RAPID_API_KEY = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_KEY")
RAPID_API_HOST = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_HOST", "rightmove-com.p.rapidapi.com")
RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT = os.environ.get(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT", 
    "/properties/rightmoveclient/property-for-sale"
)
RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT = os.environ.get(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT", 
    "/properties/rightmoveclient/properties"
)

# Test constants
TEST_PROPERTY_URL = os.environ.get("TEST_PROPERTY_URL", "https://www.rightmove.co.uk/properties/154508327")
TEST_PROPERTY_ID = "154508327"  # Default test property ID

# Function to extract property ID from URL
def extract_rightmove_property_id(url):
    """Extract the property ID from a Rightmove URL."""
    try:
        # First, try to parse the URL path directly
        path = urlparse(url).path
        if "/properties/" in path:
            segments = path.strip("/").split("/")
            idx = segments.index("properties")
            if idx + 1 < len(segments):
                return int(segments[idx + 1])
        
        # If that fails, try to get it from query parameters
        query = parse_qs(urlparse(url).query)
        if "id" in query:
            return int(query["id"][0])
        
        return None
    except (ValueError, IndexError) as e:
        print(f"Error extracting property ID from URL {url}: {str(e)}")
        return None

async def make_request(method, url, params=None, headers=None):
    """Make an HTTP request and return the response."""
    try:
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error making request: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            try:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response headers: {e.response.headers}")
                print(f"Response body: {e.response.text}")
            except:
                print("Could not print response details")
        return None

async def test_rightmove_api():
    """Test both Rightmove API endpoints and print the responses."""
    # Set up headers for RapidAPI
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": RAPID_API_HOST,
    }
    base_url = f"https://{RAPID_API_HOST}"
    
    # Extract property ID from URL if provided
    if TEST_PROPERTY_URL:
        extracted_id = extract_rightmove_property_id(TEST_PROPERTY_URL)
        property_id = str(extracted_id) if extracted_id else TEST_PROPERTY_ID
    else:
        property_id = TEST_PROPERTY_ID
    
    print(f"Testing with property ID: {property_id}")
    
    # Test properties/details endpoint
    print("\n=== Testing properties/details endpoint ===")
    endpoint1 = f"{base_url}{RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT}"
    params1 = {"propertyId": property_id}
    print(f"Making request to: {endpoint1}")
    print(f"With params: {params1}")
    
    response1 = await make_request("GET", endpoint1, params1, headers)
    if response1:
        print("Response fields:")
        for key in response1.keys():
            print(f"  - {key}")
        
        # Check for ID field specifically
        if "id" in response1:
            print(f"Found ID field: {response1['id']}")
        else:
            print("No 'id' field found in the response!")
            # Look for alternative ID fields
            for key in response1.keys():
                if "id" in key.lower():
                    print(f"Possible ID field: {key} = {response1[key]}")
        
        # Save the response to a file for further analysis
        with open("rightmove_properties_details_response.json", "w") as f:
            json.dump(response1, f, indent=2)
        print("Response saved to rightmove_properties_details_response.json")
    
    # Test property-for-sale/detail endpoint
    print("\n=== Testing property-for-sale/detail endpoint ===")
    endpoint2 = f"{base_url}{RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT}/detail"
    params2 = {"propertyId": property_id}
    print(f"Making request to: {endpoint2}")
    print(f"With params: {params2}")
    
    response2 = await make_request("GET", endpoint2, params2, headers)
    if response2:
        print("Response fields:")
        for key in response2.keys():
            print(f"  - {key}")
        
        # Check for ID field specifically
        if "id" in response2:
            print(f"Found ID field: {response2['id']}")
        else:
            print("No 'id' field found in the response!")
            # Look for alternative ID fields
            for key in response2.keys():
                if "id" in key.lower():
                    print(f"Possible ID field: {key} = {response2[key]}")
        
        # Save the response to a file for further analysis
        with open("rightmove_property_for_sale_response.json", "w") as f:
            json.dump(response2, f, indent=2)
        print("Response saved to rightmove_property_for_sale_response.json")

if __name__ == "__main__":
    # Check if we have the API key
    if not RAPID_API_KEY:
        print("Error: RAPID_API_KEY environment variable not set. Use:")
        print("export DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_KEY=your_api_key")
        exit(1)
    
    print(f"Using RAPID_API_HOST: {RAPID_API_HOST}")
    print(f"Using RAPID_API_KEY: {RAPID_API_KEY[:5]}...{RAPID_API_KEY[-5:] if RAPID_API_KEY else ''}")
    
    asyncio.run(test_rightmove_api())
