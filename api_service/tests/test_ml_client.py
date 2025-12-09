# tests/test_ml_client.py
import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from app.services import ml_client


def test_get_ml_service_base_url_env(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_URL", "http://env-ml:9000/")
    url = ml_client.get_ml_service_base_url()
    assert url == "http://env-ml:9000"


def test_get_ml_service_base_url_settings(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_URL", raising=False)

    class DummySettings:
        ML_SERVICE_URL = "http://settings-ml:9000/"
    monkeypatch.setattr("app.services.ml_client.settings", DummySettings)

    url = ml_client.get_ml_service_base_url()
    assert url == "http://settings-ml:9000"


def test_get_ml_service_base_url_default(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_URL", raising=False)
    monkeypatch.setattr("app.services.ml_client.settings", object())
    url = ml_client.get_ml_service_base_url()
    assert url == "http://ml_service:8001"


@pytest.mark.asyncio
async def test_request_wait_time_prediction_http_error():
    symptoms = ["fever"]
    queue_size = 1

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP error"))
    mock_response.json = AsyncMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch('app.services.ml_client.get_ml_service_base_url', return_value="http://ml_service:8001"):
        with patch('app.services.ml_client.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(Exception, match="HTTP error"):
                await ml_client.request_wait_time_prediction(symptoms, queue_size)
