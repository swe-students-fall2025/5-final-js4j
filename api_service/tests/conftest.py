import pytest
from fastapi.testclient import TestClient
from app.main import api_application

@pytest.fixture(scope="session")
def client():
    # lifespan runs exactly once
    with TestClient(api_application) as c:
        yield c
