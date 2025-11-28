from fastapi.testclient import TestClient
from app.main import api_application

test_client = TestClient(api_application)
"""
Shared FastAPI TestClient instance used for exercising the API endpoints
in unit tests.
"""


def test_health_check_returns_ok():
    """
    Verify that the `/health` endpoint is reachable and returns the
    expected JSON payload.
    """
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
