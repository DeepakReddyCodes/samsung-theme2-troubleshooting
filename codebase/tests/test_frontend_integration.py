"""Integration test verifying FastAPI serves the interactive frontend diagnostic portal."""
from fastapi import status
from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_frontend_index_serving(client):
    """Verify GET / returns the compiled React diagnostic portal index.html."""
    resp = client.get("/")
    assert resp.status_code == status.HTTP_200_OK
    assert "text/html" in resp.headers.get("content-type", "")
    assert '<div id="root">' in resp.text
    assert "SmartGuide" in resp.text or "Theme 02" in resp.text or "vite" in resp.text


def test_api_routes_not_shadowed_by_frontend(client):
    """Verify that official API routes remain fully functional and unshadowed."""
    # Health check must still return 200 with status: ok
    health_resp = client.get("/health")
    assert health_resp.status_code == status.HTTP_200_OK
    data = health_resp.json()
    assert data["status"] == "ok"
    assert data["ready"] is True
