"""Main FastAPI application for the ML Queue Predictor Service.

Defines endpoints for health checking and wait time predictions based
on patient symptoms and queue size.
"""

from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
from .predictor import predict_wait_time

ml_application = FastAPI(title="ML Queue Predictor Service")


class PredictionRequest(BaseModel):
    """Request schema for predicting wait time."""

    symptoms: List[str]
    queue_size: int


class PredictionResponse(BaseModel):
    """Response schema for predicted wait time and priority score."""

    predicted_wait_minutes: float
    priority_score: float


@ml_application.get("/health")
async def health_check() -> dict:
    """Health check endpoint to confirm service is running."""
    return {"status": "ok"}


@ml_application.post("/predict", response_model=PredictionResponse)
async def predict_endpoint(payload: PredictionRequest) -> PredictionResponse:
    """Predict wait time and triage priority based on symptoms and queue size.

    Parameters
    ----------
    payload : PredictionRequest
        The list of symptoms and current queue size.

    Returns
    -------
    PredictionResponse
        Contains the predicted wait time and computed priority score.
    """
    prediction = predict_wait_time(
        selected_symptoms=payload.symptoms,
        queue_size=payload.queue_size,
    )
    return PredictionResponse(**prediction)
