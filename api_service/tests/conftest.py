# import pytest
# from fastapi.testclient import TestClient
# from app.main import api_application

# @pytest.fixture(scope="session")
# def client():
#     # lifespan runs exactly once
#     with TestClient(api_application) as c:
#         yield c

# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from bson import ObjectId

from app.main import api_application


@pytest.fixture
def mock_db(monkeypatch):
    mock_patients = AsyncMock()
    mock_doctors = AsyncMock()

    mock_patients.find_one.return_value = None
    mock_doctors.find_one.return_value = None

    class InsertResult:
        inserted_id = ObjectId()

    mock_patients.insert_one.return_value = InsertResult()
    mock_doctors.insert_one.return_value = InsertResult()

    db = {
        "patients": mock_patients,
        "doctors": mock_doctors,
    }

    monkeypatch.setattr("app.main.get_database", lambda: db)

    return db


@pytest.fixture
async def client(mock_db):
    transport = ASGITransport(app=api_application)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as ac:
        yield ac, mock_db
