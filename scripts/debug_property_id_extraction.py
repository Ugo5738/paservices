#!/usr/bin/env python3
"""
Debug script to investigate property ID extraction from Rightmove API responses.
This script dumps the full structure of both API responses to help identify
where the property ID is stored in the nested structure.
"""

import os
import asyncio
import json
import uuid
import httpx
from pprint import pprint
from typing import Dict, Any, Optional

# Docker service URLs for inter-container communication
DATA_CAPTURE_SERVICE_URL = "http://data_capture_rightmove_service:8000"

# Test constants
TEST_PROPERTY_URL = "https://www.rightmove.co.uk/properties/154508327"
TEST_PROPERTY_ID = "154508327"  # Default test property ID

async def extract_and_print_api_response():
    """
    Make a direct API request to the data capture service and print out the full
    response structure to help debug property ID extraction.
    """
    # Generate a random UUID to use as the Super ID
    random_super_id = str(uuid.uuid4())
    print(f"Generated random UUID: {random_super_id}")
    
    # The property fetch endpoint is available at /api/v1/properties/fetch/combined
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
    
    print(f"Requesting property data from: {url}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:  # Longer timeout for property data
            response = await client.post(
                url,
                json={
                    "property_url": TEST_PROPERTY_URL,
                    "super_id": random_super_id,
                    "description": "Debug property ID extraction"
                }
            )
            
            response.raise_for_status()
            property_data = response.json()
            
            # Save complete response to a file for analysis
            with open("/app/debug_response.json", "w") as f:
                json.dump(property_data, f, indent=2)
                
            print("✅ Successfully fetched property data and saved to debug_response.json")
            
            # Pretty print the high-level response structure
            print("\n📋 High-level property data structure:")
            print(f"Property ID from response: {property_data.get('property_id')}")
            print(f"Property URL: {property_data.get('property_url')}")
            
            # For each API endpoint result
            for result in property_data.get('results', []):
                endpoint = result.get('api_endpoint', 'unknown')
                stored = result.get('stored', False)
                message = result.get('message', 'No message')
                super_id = result.get('super_id', 'No super_id')
                
                print(f"\n=== API Endpoint: {endpoint} ===")
                print(f"Stored: {'✅ Yes' if stored else '❌ No'}")
                print(f"Super ID: {super_id}")
                print(f"Message: {message}")
                
            # Now let's make direct API calls to get the raw responses
            print("\n🔍 Making direct API calls to get raw responses...")
            
            # 1. Call the properties/details endpoint
            details_url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/details/{TEST_PROPERTY_ID}"
            print(f"\nCalling properties/details API: {details_url}")
            
            details_response = await client.get(details_url)
            details_data = details_response.json() if details_response.status_code == 200 else {}
            
            # Save the raw response to a file
            with open("/app/properties_details_raw.json", "w") as f:
                json.dump(details_data, f, indent=2)
                
            print("✅ Saved raw properties/details response to properties_details_raw.json")
            
            # Print the top-level structure
            if details_data:
                print("\nProperties/Details API Response Structure:")
                print("Top-level keys:")
                pprint(list(details_data.keys()))
                
                # Check if there's a nested data field
                if "data" in details_data and isinstance(details_data["data"], dict):
                    print("\nNested data keys:")
                    pprint(list(details_data["data"].keys()))
                    
                    # Look for potential property ID fields
                    id_fields = ["id", "propertyId", "property_id"]
                    for field in id_fields:
                        if field in details_data["data"]:
                            print(f"\nFound potential ID field '{field}': {details_data['data'][field]}")
                
            # 2. Call the property-for-sale/detail endpoint
            sale_url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/property-for-sale/{TEST_PROPERTY_ID}"
            print(f"\nCalling property-for-sale/detail API: {sale_url}")
            
            sale_response = await client.get(sale_url)
            sale_data = sale_response.json() if sale_response.status_code == 200 else {}
            
            # Save the raw response to a file
            with open("/app/property_for_sale_raw.json", "w") as f:
                json.dump(sale_data, f, indent=2)
                
            print("✅ Saved raw property-for-sale response to property_for_sale_raw.json")
            
            # Print the top-level structure
            if sale_data:
                print("\nProperty-For-Sale API Response Structure:")
                print("Top-level keys:")
                pprint(list(sale_data.keys()))
                
                # Check if there's a nested data field
                if "data" in sale_data and isinstance(sale_data["data"], dict):
                    print("\nNested data keys:")
                    pprint(list(sale_data["data"].keys()))
                    
                    # Look for potential property ID fields
                    id_fields = ["id", "propertyId", "property_id"]
                    for field in id_fields:
                        if field in sale_data["data"]:
                            print(f"\nFound potential ID field '{field}': {sale_data['data'][field]}")
            
    except Exception as e:
        print(f"❌ Error fetching property data: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text[:500]}...")  # Print first 500 chars

async def main():
    """Main function to run the debug script"""
    print("=" * 50)
    print("RIGHTMOVE API PROPERTY ID EXTRACTION DEBUG")
    print("=" * 50)
    
    await extract_and_print_api_response()
    print("\n✨ Debug completed! ✨")

if __name__ == "__main__":
    asyncio.run(main())
