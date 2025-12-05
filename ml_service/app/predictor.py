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

HIGH_RISK_SYMPTOMS = {
    "shortness_of_breath",
    "chest_pain",
}

MEDIUM_RISK_SYMPTOMS = {
    "fever",
    "vomiting",
    "diarrhea",
}


def build_feature_vector(selected_symptoms: List[str], queue_size: int) -> np.ndarray:
    """
    Turn symptom checkbox values plus queue size into a numeric feature vector.

    Feature layout:
        [
            queue_size,
            fever_flag,
            cough_flag,
            ...,
            diarrhea_flag,
            other_flag
        ]
    """
    selected_lower = {symptom_name.lower() for symptom_name in selected_symptoms}

    symptom_flags: List[float] = []
    for canonical_name in SYMPTOM_NAMES:
        symptom_flags.append(1.0 if canonical_name in selected_lower else 0.0)

    feature_values: List[float] = [float(queue_size)] + symptom_flags
    return np.array(feature_values, dtype=float)


def estimate_urgency_score(selected_symptoms: List[str]) -> float:
    """
    Rule-based urgency score used only for generating synthetic labels.
    """
    urgency_score = 1.0
    selected_lower = {symptom_name.lower() for symptom_name in selected_symptoms}

    for symptom_name in selected_lower:
        if symptom_name in HIGH_RISK_SYMPTOMS:
            urgency_score += 3.0
        elif symptom_name in MEDIUM_RISK_SYMPTOMS:
            urgency_score += 2.0
        else:
            urgency_score += 0.5

    if urgency_score > 10.0:
        urgency_score = 10.0

    return urgency_score


def simulate_true_wait_time(selected_symptoms: List[str], queue_size: int) -> float:
    """
    Hidden 'true' function that the model tries to approximate.
    """
    base_minutes_per_patient = 10.0
    people_ahead_in_queue = max(queue_size - 1, 0)

    urgency_score = estimate_urgency_score(selected_symptoms)

    # Higher urgency => smaller multiplier
    severity_multiplier = 1.6 - 0.1 * urgency_score
    if severity_multiplier < 0.4:
        severity_multiplier = 0.4

    wait_without_noise = (
        people_ahead_in_queue * base_minutes_per_patient * severity_multiplier
    )

    noise_component = random.gauss(0.0, 4.0)
    simulated_wait = max(wait_without_noise + noise_component, 0.0)

    return simulated_wait


def build_training_set(sample_count: int) -> Tuple[np.ndarray, np.ndarray]:
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

    for sample_index in range(sample_count):
        # Sample random symptoms
        selected_symptoms: List[str] = []
        basic_symptom_count = random.randint(1, 3)
        for basic_index in range(basic_symptom_count):
            selected_symptoms.append(random.choice(possible_basic_symptoms))

        if random.random() < 0.25:
            selected_symptoms.append("shortness_of_breath")
        if random.random() < 0.15:
            selected_symptoms.append("chest_pain")
        if random.random() < 0.2:
            selected_symptoms.append("other")

        queue_size = random.randint(1, 30)

        feature_vector = build_feature_vector(selected_symptoms, queue_size)
        simulated_wait = simulate_true_wait_time(selected_symptoms, queue_size)

        feature_rows.append(feature_vector)
        target_values.append(simulated_wait)

    feature_matrix = np.vstack(feature_rows)
    target_vector = np.array(target_values, dtype=float)
    return feature_matrix, target_vector


def train_model() -> RandomForestRegressor:
    """
    Train a small RandomForest model on synthetic data.

    This runs at import time so tests and the service work out of the box.
    """
    random.seed(42)
    np.random.seed(42)

    sample_count = 2000
    feature_matrix, target_vector = build_training_set(sample_count)

    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(feature_matrix, target_vector)
    return model


MODEL: RandomForestRegressor = train_model()


def predict_wait_time(
    selected_symptoms: List[str], queue_size: int
) -> Dict[str, float]:
    """
    Public function used by the FastAPI endpoint and tests.

    Returns:
        {
            "predicted_wait_minutes": float,
            "priority_score": float
        }
    """
    feature_vector = build_feature_vector(selected_symptoms, queue_size)
    feature_matrix = feature_vector.reshape(1, -1)
    predicted_array = MODEL.predict(feature_matrix)
    predicted_wait_minutes = float(predicted_array[0])

    # Derive priority score from predicted wait:
    # lower wait => higher priority (between 1 and 10).
    if predicted_wait_minutes <= 0.0:
        priority_score = 10.0
    else:
        scaled_value = 60.0 / predicted_wait_minutes
        if scaled_value > 10.0:
            priority_score = 10.0
        elif scaled_value < 1.0:
            priority_score = 1.0
        else:
            priority_score = scaled_value

    return {
        "predicted_wait_minutes": predicted_wait_minutes,
        "priority_score": priority_score,
    }
