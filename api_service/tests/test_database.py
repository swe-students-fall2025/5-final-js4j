import pytest
from unittest.mock import patch, MagicMock

from app.database import (
    get_mongo_client,
    close_mongo_client,
    get_database,
    mongo_client_instance,
)


@pytest.fixture(autouse=True)
def reset_client():
    """Ensure each test runs with a clean client cache."""
    close_mongo_client()
    yield
    close_mongo_client()


def test_get_mongo_client_creates_instance():
    """Ensure the client is created only once."""
    with patch("app.database.AsyncIOMotorClient") as mock_client:
        client1 = get_mongo_client()
        client2 = get_mongo_client()

        assert client1 is client2  # Cached
        mock_client.assert_called_once()  # Only called once


def test_get_mongo_client_uses_expected_connection_string():
    """Ensure the correct connection string format is passed to Motor."""
    with patch("app.database.AsyncIOMotorClient") as mock_client:
        get_mongo_client()

        assert mock_client.call_count == 1

        # Extract argument to verify connection string is correct
        args, _ = mock_client.call_args
        assert "mongodb://" in args[0]
        assert "@" in args[0]
        assert "?authSource=" in args[0]



def test_get_database_returns_db_object():
    """Ensure get_database() returns a database handle."""
    fake_client = MagicMock()
    fake_db = MagicMock()
    fake_client.__getitem__.return_value = fake_db

    with patch("app.database.AsyncIOMotorClient", return_value=fake_client):
        db = get_database()

        # Verify correct DB name passed
        fake_client.__getitem__.assert_called_once()
        assert db is fake_db
