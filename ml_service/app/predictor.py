"""Predictor module for estimating patient wait times and urgency scores.

This module provides:
- Feature vector construction from symptoms and queue size
- Synthetic data generation and training of a RandomForest model
- Prediction of wait time and priority score for the ML service
"""

from typing import List, Dict, Tuple
import random

import numpy as np
from sklearn.ensemble import RandomForestRegressor


SYMPTOM_NAMES: List[str] = [
    "fever",
    "cough",
    "fatigue",
    "nausea",
    "headache",
    "sore_throat",
    "shortness_of_breath",
    "chest_pain",
    "congestion",
    "vomiting",
    "diarrhea",
    "other",
]

HIGH_RISK_SYMPTOMS = {"shortness_of_breath", "chest_pain"}
MEDIUM_RISK_SYMPTOMS = {"fever", "vomiting", "diarrhea"}


def build_feature_vector(selected_symptoms: List[str], queue_size: int) -> np.ndarray:
    """Convert symptoms and queue size into a numeric feature vector."""
    selected_lower = {s.lower() for s in selected_symptoms}
    symptom_flags = [1.0 if name in selected_lower else 0.0 for name in SYMPTOM_NAMES]
    return np.array([float(queue_size)] + symptom_flags, dtype=float)


def estimate_urgency_score(selected_symptoms: List[str]) -> float:
    """Compute a rule-based urgency score (for synthetic label generation)."""
    urgency_score = 1.0
    selected_lower = {s.lower() for s in selected_symptoms}

    for symptom_name in selected_lower:
        if symptom_name in HIGH_RISK_SYMPTOMS:
            urgency_score += 3.0
        elif symptom_name in MEDIUM_RISK_SYMPTOMS:
            urgency_score += 2.0
        else:
            urgency_score += 0.5

    return min(urgency_score, 10.0)


def simulate_true_wait_time(selected_symptoms: List[str], queue_size: int) -> float:
    """Simulate the 'true' wait time for synthetic data generation."""
    base_minutes_per_patient = 10.0
    people_ahead = max(queue_size - 1, 0)
    urgency_score = estimate_urgency_score(selected_symptoms)

    severity_multiplier = max(1.6 - 0.1 * urgency_score, 0.4)
    wait_without_noise = people_ahead * base_minutes_per_patient * severity_multiplier

    noise_component = random.gauss(0.0, 4.0)
    return max(wait_without_noise + noise_component, 0.0)


def build_training_set(sample_count: int) -> Tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data for the RandomForest model."""
    feature_rows: List[np.ndarray] = []
    target_values: List[float] = []

    possible_basic_symptoms = [
        "fever",
        "cough",
        "fatigue",
        "nausea",
        "headache",
        "sore_throat",
        "congestion",
        "vomiting",
        "diarrhea",
    ]

    for _ in range(sample_count):
        # select 1-3 random basic symptoms
        basic_symptom_count = random.randint(1, 3)
        selected_symptoms: List[str] = random.sample(
            possible_basic_symptoms, k=basic_symptom_count
        )

        if random.random() < 0.25:
            selected_symptoms.append("shortness_of_breath")
        if random.random() < 0.15:
            selected_symptoms.append("chest_pain")
        if random.random() < 0.2:
            selected_symptoms.append("other")

        queue_size = random.randint(1, 30)
        feature_rows.append(build_feature_vector(selected_symptoms, queue_size))
        target_values.append(simulate_true_wait_time(selected_symptoms, queue_size))

    return np.vstack(feature_rows), np.array(target_values, dtype=float)


def train_model() -> RandomForestRegressor:
    """Train the RandomForest model on synthetic data."""
    random.seed(42)
    np.random.seed(42)

    feature_matrix, target_vector = build_training_set(2000)

    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(feature_matrix, target_vector)
    return model


MODEL: RandomForestRegressor = train_model()


def predict_wait_time(selected_symptoms: List[str], queue_size: int) -> Dict[str, float]:
    """Predict wait time and priority score from symptoms and queue size."""
    feature_vector = build_feature_vector(selected_symptoms, queue_size)
    feature_matrix = feature_vector.reshape(1, -1)
    predicted_array = MODEL.predict(feature_matrix)
    predicted_wait = float(predicted_array[0])

    # lower wait => higher priority (1-10)
    if predicted_wait <= 0.0:
        priority_score = 10.0
    else:
        scaled_value = 60.0 / predicted_wait
        priority_score = min(max(scaled_value, 1.0), 10.0)

    return {
        "predicted_wait_minutes": predicted_wait,
        "priority_score": priority_score,
    }
