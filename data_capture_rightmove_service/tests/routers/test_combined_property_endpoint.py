"""
Tests for the combined property endpoints in property_router.
"""
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.routers.property_router import router


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app with the property router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator:
    """Get test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_db_session():
    """Create a mock DB session."""
    return AsyncMock(AsyncSession)


@pytest.fixture
def mock_super_id_client():
    """Mock the super_id_service_client."""
    with patch("data_capture_rightmove_service.routers.property_router.super_id_service_client") as mock:
        mock.create_super_id = AsyncMock(return_value=uuid.uuid4())
        yield mock


@pytest.fixture
def mock_rightmove_api_client():
    """Mock the rightmove_api_client."""
    with patch("data_capture_rightmove_service.routers.property_router.rightmove_api_client") as mock:
        # Sample data structures that match expected API responses
        mock.get_property_details = AsyncMock(return_value={
            "propertyId": 123456789,
            "transactionType": "SALE",
            "bedrooms": 3,
            "price": {"amount": 350000, "qualifier": "Guide Price"},
            "agent": {
                "branchId": 12345,
                "branchName": "Test Agent",
                "branchLogoUrl": "https://example.com/logo.jpg",
            },
            "propertyImages": {
                "images": [
                    {"url": "https://example.com/image1.jpg", "caption": "Front view"},
                    {"url": "https://example.com/image2.jpg", "caption": "Kitchen"},
                ]
            },
            "floorplans": [
                {"url": "https://example.com/floorplan.jpg"}
            ],
        })
        
        mock.get_property_for_sale_details = AsyncMock(return_value={
            "id": 123456789,
            "propertyType": "Detached house",
            "bedrooms": 3,
            "summary": "A beautiful 3 bed detached house",
            "price": {
                "currencyCode": "GBP",
                "displayPrice": "£350,000",
                "priceQualifier": "Guide Price",
            },
            "customer": {
                "branchId": 12345,
                "branchName": "Test Agent",
                "companyName": "Test Company",
                "branchLogo": "https://example.com/logo.jpg",
            },
            "images": [
                {"url": "https://example.com/image1.jpg", "caption": "Front view"},
                {"url": "https://example.com/image2.jpg", "caption": "Kitchen"},
            ],
            "floorplans": [
                {"url": "https://example.com/floorplan.jpg", "caption": "Floor 1"},
            ],
        })
        
        yield mock


@pytest.fixture
def mock_store_functions():
    """Mock the database store functions."""
    with patch("data_capture_rightmove_service.routers.property_router.store_properties_details") as mock_store_properties:
        with patch("data_capture_rightmove_service.routers.property_router.store_property_details") as mock_store_property:
            mock_store_properties.return_value = (True, "Successfully stored properties details")
            mock_store_property.return_value = (True, "Successfully stored property details")
            
            yield mock_store_properties, mock_store_property


@pytest.mark.asyncio
async def test_fetch_combined_with_property_id(
    client, 
    mock_db_session, 
    mock_super_id_client, 
    mock_rightmove_api_client, 
    mock_store_functions
):
    """Test the combined fetch endpoint with a property ID."""
    # Override dependency
    app = client.app
    app.dependency_overrides = {
        "get_db": lambda: mock_db_session,
    }
    
    # Make the request
    response = await client.post(
        "/properties/fetch/combined",
        json={"property_id": 123456789}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert data["property_id"] == 123456789
    assert "results" in data
    assert len(data["results"]) == 2
    
    # Verify API calls
    mock_rightmove_api_client.get_property_details.assert_called_once_with("123456789")
    mock_rightmove_api_client.get_property_for_sale_details.assert_called_once_with("123456789")
    
    # Verify storage calls
    mock_store_properties, mock_store_property = mock_store_functions
    mock_store_properties.assert_called_once()
    mock_store_property.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_combined_with_property_url(
    client, 
    mock_db_session, 
    mock_super_id_client, 
    mock_rightmove_api_client, 
    mock_store_functions
):
    """Test the combined fetch endpoint with a property URL."""
    # Override dependency
    app = client.app
    app.dependency_overrides = {
        "get_db": lambda: mock_db_session,
    }
    
    # Make the request with a URL
    test_url = "https://www.rightmove.co.uk/properties/123456789#/?channel=RES_BUY"
    response = await client.post(
        "/properties/fetch/combined",
        json={"property_url": test_url}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert data["property_id"] == 123456789
    assert data["property_url"] == test_url
    assert "results" in data
    assert len(data["results"]) == 2
    
    # Verify API calls - should use extracted ID
    mock_rightmove_api_client.get_property_details.assert_called_once_with("123456789")
    mock_rightmove_api_client.get_property_for_sale_details.assert_called_once_with("123456789")
    
    # Verify storage calls
    mock_store_properties, mock_store_property = mock_store_functions
    mock_store_properties.assert_called_once()
    mock_store_property.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_combined_invalid_url(
    client, 
    mock_db_session
):
    """Test the combined fetch endpoint with an invalid URL."""
    # Override dependency
    app = client.app
    app.dependency_overrides = {
        "get_db": lambda: mock_db_session,
    }
    
    # Make the request with an invalid URL
    response = await client.post(
        "/properties/fetch/combined",
        json={"property_url": "https://www.example.com/not-rightmove"}
    )
    
    # Check response is an error
    assert response.status_code == 400
    data = response.json()
    assert "Failed to extract property ID" in data["detail"]


@pytest.mark.asyncio
async def test_fetch_combined_no_identifiers(
    client, 
    mock_db_session
):
    """Test the combined fetch endpoint with no property identifiers."""
    # Override dependency
    app = client.app
    app.dependency_overrides = {
        "get_db": lambda: mock_db_session,
    }
    
    # Make the request with no identifiers
    response = await client.post(
        "/properties/fetch/combined",
        json={"description": "Test property"}
    )
    
    # Check response is an error
    assert response.status_code == 400
    data = response.json()
    assert "Either property_id or property_url must be provided" in data["detail"]


@pytest.mark.asyncio
async def test_validate_url_endpoint_valid_url(client):
    """Test the URL validation endpoint with a valid URL."""
    response = await client.get(
        "/properties/validate-url",
        params={"url": "https://www.rightmove.co.uk/properties/123456789"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["property_id"] == 123456789


@pytest.mark.asyncio
async def test_validate_url_endpoint_invalid_url(client):
    """Test the URL validation endpoint with an invalid URL."""
    response = await client.get(
        "/properties/validate-url",
        params={"url": "https://www.example.com/not-rightmove"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["property_id"] is None
