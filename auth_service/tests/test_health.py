import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_response_data():
    """Generate mock health check response data"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": "test",
        "timestamp": "2023-01-01T00:00:00Z",
        "components": {
            "api": {"status": "ok"},
            "database": {"status": "ok"},
            "supabase": {"status": "ok"}
        }
    }


@pytest.mark.asyncio
async def test_health_ok():
    from auth_service.main import health
    
    # Create mocks
    mock_db = AsyncMock()
    mock_db.execute.return_value.first.return_value = type('Row', (), {"1": 1})()
    
    mock_supabase = AsyncMock()
    mock_supabase.auth = AsyncMock()
    
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "test-agent"
    
    # Execute the health check function with our mocks
    response = await health(mock_request, db=mock_db, supabase_general_client=mock_supabase)
    
    # Verify response is JSONResponse type
    from fastapi.responses import JSONResponse
    assert isinstance(response, JSONResponse)
    
    # Extract the response content
    response_data = response.body.decode('utf-8')
    import json
    response_json = json.loads(response_data)
    
    # Verify the response content
    assert response_json["status"] == "ok"
    assert "version" in response_json
    assert "components" in response_json
    assert response_json["components"]["api"]["status"] == "ok"
    
    # Database status might be 'ok' or 'skipped' depending on check interval
    assert response_json["components"]["database"]["status"] in ["ok", "skipped"]
    assert "supabase" in response_json["components"]


# Test for method not allowed handled by FastAPI itself
def test_invalid_method_handling():
    # FastAPI handles this automatically, so just verify that behavior
    app = FastAPI()
    
    @app.get("/test")
    def test_endpoint():
        return {"hello": "world"}
    
    # FastAPI will return 405 for non-allowed methods
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    response = client.post("/test")  # POST not allowed on a GET endpoint
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}
