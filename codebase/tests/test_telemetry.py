import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_cors_telemetry_headers_exposed():
    """Verify that telemetry headers are exposed via CORS."""
    client = TestClient(app)

    # Send an OPTIONS request to trigger CORS preflight handling
    response = client.options(
        "/v1/troubleshoot",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200

    # Use context manager to properly trigger lifespan startup/ready state
    with TestClient(app) as client:
        payload = {
            "query": "Test query",
            "siis_response": {
                "title": "Test Title",
                "content": "Test content"
            }
        }

        post_resp = client.post(
            "/v1/troubleshoot",
            json=payload,
            headers={"Origin": "http://localhost:3000"}
        )

        assert post_resp.status_code == 200
        exposed_headers = post_resp.headers.get("access-control-expose-headers", "").lower()

    assert "x-process-time-ms" in exposed_headers
    assert "x-cache-time-ms" in exposed_headers
    assert "x-extract-time-ms" in exposed_headers
    assert "x-serialize-time-ms" in exposed_headers
