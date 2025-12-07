"""Client module for interacting with the external ML service for wait time predictions."""

from typing import List, Dict
import os

import httpx
from app.config import settings  # global settings instance


def get_ml_service_base_url() -> str:
    """
    Determine the base URL for the ML service.

    Returns
    -------
    str
        The URL to use for HTTP requests to the ML service.
        It checks in order: environment variable, config settings, then default.
    """
    environment_url = os.getenv("ML_SERVICE_URL")
    if environment_url:
        return environment_url.rstrip("/")

    if hasattr(settings, "ML_SERVICE_URL"):
        return settings.ML_SERVICE_URL.rstrip("/")

    # Default fallback
    return "http://ml_service:8001"


async def request_wait_time_prediction(
    symptom_names: List[str],
    queue_size: int,
) -> Dict[str, float]:
    """
    Request a predicted wait time from the ML service.

    Parameters
    ----------
    symptom_names : List[str]
        List of patient symptom identifiers.
    queue_size : int
        Number of patients currently in the queue (including the new patient).

    Returns
    -------
    Dict[str, float]
        JSON response from the ML service containing the predicted wait time.
    """
    base_url = get_ml_service_base_url()
    request_body = {
        "symptoms": symptom_names,
        "queue_size": queue_size,
    }

    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(f"{base_url}/predict", json=request_body, timeout=5.0)
        response.raise_for_status()
        return response.json()
