import pytest
from fastapi.testclient import TestClient

from auth_service.main import app

client = TestClient(app)

def test_error_example_handler():
    response = client.get("/error")
    assert response.status_code == 400
    assert response.json() == {"detail": "Custom error"}


def test_validation_exception_handler_missing_field():
    response = client.post("/echo", json={})
    assert response.status_code == 422
    json_data = response.json()
    assert "detail" in json_data
    missing_errors = [err for err in json_data["detail"] if err.get("type") == "missing" and err.get("loc", [])[ -1 ] == "message"]
    assert missing_errors, "Missing field 'message' error not found"


def test_validation_exception_handler_invalid_type():
    response = client.post("/echo", json={"message": 123})
    assert response.status_code == 422
    json_data = response.json()
    assert "detail" in json_data
    type_errors = [
        err
        for err in json_data["detail"]
        if err.get("loc", [])[ -1 ] == "message"
        and (
            err.get("type", "").startswith("type_error")
            or err.get("type") == "string_type"
        )
    ]
    assert type_errors, "Type error for field 'message' not found"
