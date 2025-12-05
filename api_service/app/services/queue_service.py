from typing import List, Dict, Any

from bson import ObjectId

from app.database import get_database
from app.services.ml_client import request_wait_time_prediction


VERY_URGENT_SYMPTOMS = {
    "chest_pain",
    "shortness_of_breath",
    "unconscious",
    "difficulty_breathing",
}

MEDIUM_URGENT_SYMPTOMS = {
    "fever",
    "vomiting",
    "diarrhea",
}


def compute_triage_priority(symptom_names: List[str]) -> float:
    """
    Deterministic triage score based ONLY on symptoms.

    Higher score = more urgent.
    """
    score = 0.0
    lower_symptoms = {symptom_name.lower() for symptom_name in symptom_names}

    for symptom_name in lower_symptoms:
        if symptom_name in VERY_URGENT_SYMPTOMS:
            score += 5.0
        elif symptom_name in MEDIUM_URGENT_SYMPTOMS:
            score += 3.0
        else:
            score += 1.0

    if score <= 0.0:
        score = 1.0
    if score > 10.0:
        score = 10.0

    return score


async def create_appointment_for_patient(
    patient_id: ObjectId,
    symptom_names: List[str],
) -> Dict[str, Any]:
    """
    Create a new appointment and insert it into the queue based on triage priority.

    - Triage priority decides queue_number.
    - ML prediction is used to estimate "minutes per patient".
    - ETA = people ahead * minutes_per_patient * severity_factor.
    """

    database_connection = get_database()
    appointment_collection = database_connection["appointments"]

    # Current waiting appointments in queue order
    existing_waiting_appointments: List[Dict[str, Any]] = await (
        appointment_collection.find({"status": "waiting"})
        .sort("queue_number", 1)
        .to_list(length=1000)
    )

    # 1) Compute deterministic triage priority for the new patient
    new_triage_priority = compute_triage_priority(symptom_names)

    # 2) Ask ML service what a "typical" total wait would be if this
    #    patient were at the END of the queue of this size.
    full_queue_size = len(existing_waiting_appointments) + 1
    ml_prediction = await request_wait_time_prediction(
        symptom_names=symptom_names,
        queue_size=full_queue_size,
    )
    ml_total_wait_estimate = float(ml_prediction["predicted_wait_minutes"])

    # Derive an average "minutes per patient" from the ML estimate.
    people_ahead_if_last = max(full_queue_size - 1, 1)
    if ml_total_wait_estimate > 0.0:
        minutes_per_patient = ml_total_wait_estimate / float(people_ahead_if_last)
    else:
        minutes_per_patient = 10.0  # sensible default fallback

    # 3) Decide where to insert in the queue based on triage priority
    insertion_index = len(existing_waiting_appointments)  # default: end

    for index, existing_appointment in enumerate(existing_waiting_appointments):
        existing_triage_priority = existing_appointment.get("triage_priority")
        if existing_triage_priority is None:
            existing_symptoms = existing_appointment.get("symptoms", [])
            existing_triage_priority = compute_triage_priority(existing_symptoms)

        if new_triage_priority > float(existing_triage_priority):
            insertion_index = index
            break

    insertion_position = insertion_index + 1  # queue_number is 1-based
    people_ahead_in_queue = insertion_position - 1

    # 4) Severity factor: urgent patients wait less even with same queue position
    if new_triage_priority >= 8.0:
        severity_factor = 0.5  # very urgent: half the usual wait
    elif new_triage_priority >= 5.0:
        severity_factor = 0.75  # medium urgent: 25% reduction
    else:
        severity_factor = 1.0  # mild: normal wait

    predicted_wait_minutes = (
        minutes_per_patient * float(people_ahead_in_queue) * severity_factor
    )

    # 5) Shift everyone at or behind this position
    await appointment_collection.update_many(
        {
            "status": "waiting",
            "queue_number": {"$gte": insertion_position},
        },
        {"$inc": {"queue_number": 1}},
    )

    # 6) Insert the new appointment with its final queue_number and ETA
    appointment_document: Dict[str, Any] = {
        "patient_id": patient_id,
        "symptoms": symptom_names,
        "status": "waiting",
        "queue_number": insertion_position,
        "predicted_wait_minutes": predicted_wait_minutes,
        "triage_priority": new_triage_priority,
    }

    insert_result = await appointment_collection.insert_one(appointment_document)
    appointment_document["_id"] = insert_result.inserted_id

    return appointment_document
