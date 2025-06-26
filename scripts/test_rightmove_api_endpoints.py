#!/usr/bin/env python3
"""
Debug script to test the Rightmove API endpoints with the correct parameters.
This script will:
1. Test the properties/details endpoint with 'identifier' parameter
2. Test the buy/property-for-sale/detail endpoint with 'id' parameter
"""

import os
import asyncio
import json
import httpx
from typing import Dict, Any

# Configuration
RAPID_API_KEY = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_KEY")
RAPID_API_HOST = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_HOST", "uk-real-estate-rightmove.p.rapidapi.com")
TEST_PROPERTY_ID = "154508327"  # Default test property ID
TEST_ALT_PROPERTY_ID = "126451514"  # Alternative test property ID from user's example

async def test_api_endpoints():
    """Test both Rightmove API endpoints with the correct parameters"""
    # Set up headers for RapidAPI
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": RAPID_API_HOST,
    }
    
    base_url = f"https://{RAPID_API_HOST}"
    
    print(f"Using RapidAPI Host: {RAPID_API_HOST}")
    print(f"Using RapidAPI Key: {RAPID_API_KEY[:5]}...{RAPID_API_KEY[-5:] if RAPID_API_KEY else ''}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Test properties/details endpoint with 'identifier' parameter
        details_endpoint = f"{base_url}/properties/details"
        details_params = {"identifier": TEST_PROPERTY_ID}
        
        print(f"\n=== Testing properties/details endpoint ===")
        print(f"URL: {details_endpoint}")
        print(f"Params: {details_params}")
        
        try:
            details_response = await client.get(
                details_endpoint,
                params=details_params,
                headers=headers
            )
            
            details_response.raise_for_status()
            details_data = details_response.json()
            
            # Save full response to file
            with open("/app/properties_details_correct.json", "w") as f:
                json.dump(details_data, f, indent=2)
                
            print("\nProperties/Details Response Summary:")
            print(f"Status Code: {details_response.status_code}")
            print(f"Response Size: {len(details_response.content)} bytes")
            print(f"Top-level keys: {list(details_data.keys())}")
            
            # Analyze the data field
            print("\nAnalyzing 'data' field:")
            if "data" in details_data:
                data_field = details_data["data"]
                data_type = type(data_field).__name__
                print(f"Data type: {data_type}")
                
                if data_type == "dict":
                    print(f"Data keys: {list(data_field.keys())}")
                    # Look for ID fields
                    for id_field in ["id", "propertyId", "property_id"]:
                        if id_field in data_field:
                            print(f"Found ID field '{id_field}': {data_field[id_field]}")
            
            # Check status and message
            if "status" in details_data:
                print(f"Status: {details_data['status']}")
            if "message" in details_data:
                print(f"Message: {details_data['message']}")
                
        except Exception as e:
            print(f"Error testing properties/details endpoint: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text[:500]}...")

        # 2. Test buy/property-for-sale/detail endpoint with 'id' parameter
        # Use the alternative property ID from the user's example
        sale_endpoint = f"{base_url}/buy/property-for-sale/detail"
        sale_params = {"id": TEST_ALT_PROPERTY_ID}
        
        print(f"\n=== Testing buy/property-for-sale/detail endpoint ===")
        print(f"URL: {sale_endpoint}")
        print(f"Params: {sale_params}")
        
        try:
            sale_response = await client.get(
                sale_endpoint,
                params=sale_params,
                headers=headers
            )
            
            sale_response.raise_for_status()
            sale_data = sale_response.json()
            
            # Save full response to file
            with open("/app/property_for_sale_correct.json", "w") as f:
                json.dump(sale_data, f, indent=2)
                
            print("\nProperty-for-sale/detail Response Summary:")
            print(f"Status Code: {sale_response.status_code}")
            print(f"Response Size: {len(sale_response.content)} bytes")
            print(f"Top-level keys: {list(sale_data.keys())}")
            
            # Analyze the data field
            print("\nAnalyzing 'data' field:")
            if "data" in sale_data:
                data_field = sale_data["data"]
                data_type = type(data_field).__name__
                print(f"Data type: {data_type}")
                
                if data_type == "dict":
                    print(f"Data keys: {list(data_field.keys())}")
                    # Look for ID fields
                    for id_field in ["id", "propertyId", "property_id"]:
                        if id_field in data_field:
                            print(f"Found ID field '{id_field}': {data_field[id_field]}")
            
            # Check status and message
            if "status" in sale_data:
                print(f"Status: {sale_data['status']}")
            if "message" in sale_data:
                print(f"Message: {sale_data['message']}")
                
        except Exception as e:
            print(f"Error testing buy/property-for-sale/detail endpoint: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text[:500]}...")

async def main():
    print("=" * 50)
    print("RIGHTMOVE API ENDPOINTS TEST")
    print("=" * 50)
    
    await test_api_endpoints()
    
    print("\n✨ Testing completed! ✨")

if __name__ == "__main__":
    asyncio.run(main())
