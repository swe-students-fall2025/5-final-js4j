from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from .predictor import predict_wait_time_and_priority

ml_application = FastAPI(title="Triage ML Service")
"""
FastAPI application instance that exposes a prediction API for triage
priority and wait-time estimation.
"""


class PredictionRequest(BaseModel):
    """
    Request body schema for the triage prediction endpoint.

    Attributes
    ----------
    symptoms : list of str
        List of symptom descriptions selected by the patient.
    """

    symptoms: List[str]


class PredictionResponse(BaseModel):
    """
    Response body schema for the triage prediction endpoint.

    Attributes
    ----------
    predicted_wait_minutes : float
        Estimated waiting time for the patient in minutes.
    priority_score : float
        Calculated priority score where higher values indicate more
        urgent cases.
    """

    predicted_wait_minutes: float
    priority_score: float


@ml_application.get("/health")
async def health_check():
    """
    Health-check endpoint for the ML service.

    Returns
    -------
    dict
        A dictionary containing a simple `"status": "ok"` message.
    """
    return {"status": "ok"}


@ml_application.post("/predict", response_model=PredictionResponse)
async def predict_endpoint(request_body: PredictionRequest):
    """
    Predict triage wait-time and priority score based on provided symptoms.

    Parameters
    ----------
    request_body : PredictionRequest
        Request data containing the list of symptoms selected by the patient.

    Returns
    -------
    PredictionResponse
        Validated response containing the predicted wait-time and
        priority score.
    """
    prediction_result = predict_wait_time_and_priority(request_body.symptoms)
    return PredictionResponse(**prediction_result)
