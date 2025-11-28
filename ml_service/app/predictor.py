from typing import Dict, List


def predict_wait_time_and_priority(symptom_list: List[str]) -> Dict[str, float]:
    """
    Compute a simple triage priority score and wait-time estimate.

    This is a rule-based placeholder for a future ML model. Symptoms
    that match a set of urgent keywords increase the priority score and
    reduce the predicted wait-time.

    Parameters
    ----------
    symptom_list : list of str
        A list of symptom descriptions selected by the patient.

    Returns
    -------
    dict
        Dictionary containing:
        - "predicted_wait_minutes": float wait-time estimate.
        - "priority_score": float priority score where higher values
          represent more urgent cases.
    """
    urgent_keywords = {"chest pain", "shortness of breath", "bleeding", "unconscious"}

    base_wait_minutes = 20.0
    priority_score = 1.0

    for symptom_description in symptom_list:
        if symptom_description.lower() in urgent_keywords:
            priority_score += 3.0

    predicted_wait_minutes = max(5.0, base_wait_minutes - priority_score * 2.0)

    return {
        "predicted_wait_minutes": predicted_wait_minutes,
        "priority_score": priority_score,
    }
