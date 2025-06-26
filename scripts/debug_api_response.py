#!/usr/bin/env python3
"""
Debug script to analyze the Rightmove API response structure in detail.
This script dumps the full API response including the data, errors, and status fields.
"""

import os
import asyncio
import json
import uuid
import httpx
from typing import Dict, Any

# Docker service names for inter-container communication
RAPID_API_KEY = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_KEY")
RAPID_API_HOST = os.environ.get("DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPID_API_HOST", "uk-real-estate-rightmove.p.rapidapi.com")

# Test constants
TEST_PROPERTY_ID = "154508327"  # Default test property ID

async def analyze_api_response():
    """
    Make direct API calls to RapidAPI Rightmove endpoints and analyze the responses.
    """
    # Set up headers for RapidAPI
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": RAPID_API_HOST,
    }
    
    base_url = f"https://{RAPID_API_HOST}"
    
    print(f"Using RapidAPI Host: {RAPID_API_HOST}")
    print(f"Using RapidAPI Key: {RAPID_API_KEY[:5]}...{RAPID_API_KEY[-5:] if RAPID_API_KEY else ''}")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Test the properties/details endpoint directly
            details_endpoint = f"{base_url}/properties/details"
            details_params = {"propertyId": TEST_PROPERTY_ID}
            
            print(f"\n=== Testing properties/details endpoint ===")
            print(f"URL: {details_endpoint}")
            print(f"Params: {details_params}")
            
            details_response = await client.get(
                details_endpoint,
                params=details_params,
                headers=headers
            )
            
            details_response.raise_for_status()
            details_data = details_response.json()
            
            # Save full response to file
            with open("/app/full_properties_details_response.json", "w") as f:
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
                elif data_type == "list" and len(data_field) > 0:
                    print(f"Data is a list with {len(data_field)} items")
                    if isinstance(data_field[0], dict):
                        print(f"First item keys: {list(data_field[0].keys())}")
                else:
                    print(f"Data content: {data_field}")
            
            # Check if there are any errors
            if "errors" in details_data:
                print("\nErrors found:")
                print(json.dumps(details_data["errors"], indent=2))
                
            # Check status
            if "status" in details_data:
                print(f"\nStatus: {details_data['status']}")
                
            # Check message
            if "message" in details_data:
                print(f"Message: {details_data['message']}")
                
            # 2. Test the property-for-sale/detail endpoint
            sale_endpoint = f"{base_url}/properties/property-for-sale/detail"
            sale_params = {"propertyId": TEST_PROPERTY_ID}
            
            print(f"\n=== Testing property-for-sale/detail endpoint ===")
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
                with open("/app/full_property_for_sale_response.json", "w") as f:
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
                    elif data_type == "list" and len(data_field) > 0:
                        print(f"Data is a list with {len(data_field)} items")
                        if isinstance(data_field[0], dict):
                            print(f"First item keys: {list(data_field[0].keys())}")
                    else:
                        print(f"Data content: {data_field}")
                
                # Check if there are any errors
                if "errors" in sale_data:
                    print("\nErrors found:")
                    print(json.dumps(sale_data["errors"], indent=2))
                    
                # Check status
                if "status" in sale_data:
                    print(f"\nStatus: {sale_data['status']}")
                    
                # Check message
                if "message" in sale_data:
                    print(f"Message: {sale_data['message']}")
            
            except Exception as e:
                print(f"Error testing property-for-sale/detail endpoint: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response status: {e.response.status_code}")
                    print(f"Response body: {e.response.text[:500]}...")
    
    except Exception as e:
        print(f"Error in analyze_api_response: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text[:500]}...")

async def main():
    print("=" * 50)
    print("RIGHTMOVE API RESPONSE ANALYSIS")
    print("=" * 50)
    
    await analyze_api_response()
    
    print("\n✨ Analysis completed! ✨")

if __name__ == "__main__":
    asyncio.run(main())
