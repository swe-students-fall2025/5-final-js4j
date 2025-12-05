from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from .predictor import predict_wait_time


ml_application = FastAPI(title="ML Queue Predictor Service")


class PredictionRequest(BaseModel):
    symptoms: List[str]
    queue_size: int


class PredictionResponse(BaseModel):
    predicted_wait_minutes: float
    priority_score: float


@ml_application.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@ml_application.post("/predict", response_model=PredictionResponse)
async def predict_endpoint(payload: PredictionRequest) -> PredictionResponse:
    prediction = predict_wait_time(
        selected_symptoms=payload.symptoms,
        queue_size=payload.queue_size,
    )
    return PredictionResponse(**prediction)
