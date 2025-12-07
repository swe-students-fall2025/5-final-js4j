"""Shared pytest fixtures for testing the API application."""

from unittest.mock import AsyncMock
from bson import ObjectId

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import api_application


@pytest.fixture
def mock_db(monkeypatch):
    """
    Create a mock MongoDB-like dictionary with async collection objects.

    This replaces the real `get_database` function during testing to prevent
    external dependencies and ensure tests run in isolation.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to patch application functions during testing.

    Returns
    -------
    dict
        A mock representation of the database, containing mock patients
        and doctors collections.
    """
    mock_patients = AsyncMock()
    mock_doctors = AsyncMock()

    mock_patients.find_one.return_value = None
    mock_doctors.find_one.return_value = None

    class InsertResult:
        """Small helper to emulate MongoDB insert_one results."""

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
async def client(mock_db):  # pylint: disable=unused-argument
    """
    Provide an async HTTP test client for the FastAPI application.

    This fixture also ensures the mock database is injected before
    the app handles any requests.

    Parameters
    ----------
    mock_db : dict
        The mock database returned by the `mock_db` fixture.

    Yields
    ------
    tuple
        A tuple containing the HTTP client and the mock database.
    """
    transport = ASGITransport(app=api_application)

    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client, mock_db
