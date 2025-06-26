"""
Mock objects and fixtures for testing.
"""
import json
import random
from typing import Dict, Any, List
import pytest
from unittest.mock import MagicMock, AsyncMock


class MockResponse:
    """Mock HTTP response for testing API requests."""
    
    def __init__(self, status_code=200, json_data=None, text=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text or json.dumps(json_data) if json_data else ""
        self.headers = headers or {}
        self.content = self.text.encode() if self.text else b""
    
    async def json(self):
        return self._json_data
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockHTTPClient:
    """Mock HTTP client for testing external API calls."""
    
    def __init__(self, responses=None):
        """
        Initialize with predefined responses or empty.
        
        Args:
            responses: Dict mapping URLs to responses
        """
        self.responses = responses or {}
        self.requests = []  # Store request history
    
    async def get(self, url, **kwargs):
        """Mock GET request."""
        self.requests.append({"method": "GET", "url": url, "kwargs": kwargs})
        
        if url in self.responses:
            return self.responses[url]
        
        # Default response if URL not specified
        return MockResponse(status_code=404, json_data={"error": "Not Found"})
    
    async def post(self, url, **kwargs):
        """Mock POST request."""
        self.requests.append({"method": "POST", "url": url, "kwargs": kwargs})
        
        if url in self.responses:
            return self.responses[url]
        
        # Default response if URL not specified
        return MockResponse(status_code=404, json_data={"error": "Not Found"})


class MockRightmoveAPI:
    """
    Mock Rightmove API client for testing without external dependencies.
    """
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        
    async def fetch_property_details(self, property_id):
        """Mock property details fetch."""
        self.calls.append({
            "method": "fetch_property_details",
            "property_id": property_id
        })
        
        # Check if we have a predefined response for this property_id
        key = f"property_details:{property_id}"
        if key in self.responses:
            return self.responses[key]
            
        # Generate a random response
        property_type = random.choice([
            "FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED", "BUNGALOW"
        ])
        bedrooms = random.randint(1, 5)
        
        # Generate mock response with essential fields
        mock_response = {
            "id": property_id,
            "transactionType": "SALE",
            "propertyType": property_type,
            "bedrooms": bedrooms,
            "address": f"{property_id} Test Street, Testville",
            "price": {
                "amount": random.randint(100000, 1000000),
                "currencyCode": "GBP",
                "displayPrice": "£450,000"
            },
            "location": {
                "latitude": 51.5074 + (random.random() - 0.5),
                "longitude": -0.1278 + (random.random() - 0.5)
            }
        }
        return mock_response
        
    async def fetch_properties_list(self, location=None, min_price=None, max_price=None, 
                                    min_bedrooms=None, max_bedrooms=None, page=1):
        """Mock properties list fetch."""
        self.calls.append({
            "method": "fetch_properties_list",
            "location": location,
            "min_price": min_price,
            "max_price": max_price,
            "min_bedrooms": min_bedrooms,
            "max_bedrooms": max_bedrooms,
            "page": page
        })
        
        # Check if we have a predefined response for this query
        query_key = f"properties_list:{location}:{min_price}-{max_price}:{min_bedrooms}-{max_bedrooms}:{page}"
        if query_key in self.responses:
            return self.responses[query_key]
            
        # Generate random number of properties (5-20)
        num_properties = random.randint(5, 20)
        properties = []
        
        for _ in range(num_properties):
            property_id = random.randint(10000000, 99999999)
            property_type = random.choice([
                "FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED", "BUNGALOW"
            ])
            bedrooms = min_bedrooms if min_bedrooms else random.randint(1, 5)
            if max_bedrooms:
                bedrooms = min(bedrooms, max_bedrooms)
                
            price = random.randint(min_price or 100000, max_price or 1000000)
            
            properties.append({
                "id": property_id,
                "transactionType": "SALE",
                "propertyType": property_type,
                "bedrooms": bedrooms,
                "displayAddress": f"Property {property_id}, {location or 'Test Location'}",
                "price": {
                    "amount": price,
                    "currencyCode": "GBP"
                }
            })
            
        mock_response = {
            "properties": properties,
            "resultCount": num_properties,
            "pageNumber": page,
            "totalPages": 5
        }
        return mock_response


@pytest.fixture
def mock_http_client():
    """Fixture that provides a mock HTTP client."""
    return MockHTTPClient()


@pytest.fixture
def mock_rightmove_api():
    """Fixture that provides a mock Rightmove API client."""
    return MockRightmoveAPI()


class MockCrud:
    """Mock CRUD operations for testing service layers without DB dependencies."""
    
    def __init__(self):
        self.calls = []
        self.returns = {}
        
    def set_return(self, method_name, value):
        """Set the return value for a specific method."""
        self.returns[method_name] = value
        
    def get_property_by_id(self, property_id):
        """Mock getting a property by ID."""
        self.calls.append({
            "method": "get_property_by_id",
            "property_id": property_id
        })
        return self.returns.get("get_property_by_id")
    
    async def create_property(self, property_data):
        """Mock creating a property."""
        self.calls.append({
            "method": "create_property",
            "property_data": property_data
        })
        return self.returns.get("create_property", property_data)
    
    async def update_property(self, property_id, property_data):
        """Mock updating a property."""
        self.calls.append({
            "method": "update_property",
            "property_id": property_id,
            "property_data": property_data
        })
        return self.returns.get("update_property", property_data)


@pytest.fixture
def mock_crud():
    """Fixture that provides a mock CRUD service."""
    return MockCrud()
