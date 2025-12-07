"""Queue service for managing patient appointments and computing triage priorities."""

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

MEDIUM_URGENT_SYMPTOMS = {"fever", "vomiting", "diarrhea"}


def compute_triage_priority(symptom_names: List[str]) -> float:
    """Compute a deterministic triage score based solely on symptoms."""
    score = sum(
        5.0 if s.lower() in VERY_URGENT_SYMPTOMS
        else 3.0 if s.lower() in MEDIUM_URGENT_SYMPTOMS
        else 1.0
        for s in set(symptom_names)
    )
    return max(1.0, min(score, 10.0))


async def _get_minutes_per_patient(symptom_names: List[str], queue_size: int) -> float:
    """Estimate average minutes per patient using ML prediction."""
    ml_prediction = await request_wait_time_prediction(
        symptom_names=symptom_names, queue_size=queue_size
    )
    total_wait = float(ml_prediction.get("predicted_wait_minutes", 0.0))
    people_ahead = max(queue_size - 1, 1)
    if total_wait > 0.0:
        return total_wait / float(people_ahead)
    return 10.0


def _determine_insertion_index(new_priority: float, appointments: List[Dict[str, Any]]) -> int:
    """Determine where in the queue the new patient should be inserted."""
    for idx, appt in enumerate(appointments):
        existing_priority = appt.get("triage_priority")
        if existing_priority is None:
            existing_priority = compute_triage_priority(appt.get("symptoms", []))
        if new_priority > float(existing_priority):
            return idx
    return len(appointments)


def _severity_factor(priority: float) -> float:
    """Return severity factor to reduce wait time for urgent patients."""
    if priority >= 8.0:
        return 0.5
    if priority >= 5.0:
        return 0.75
    return 1.0


async def create_appointment_for_patient(
    patient_id: ObjectId,
    symptom_names: List[str],
) -> Dict[str, Any]:
    """Create a new appointment and insert it into the queue based on triage priority."""
    db = get_database()
    collection = db["appointments"]

    waiting_appts = await collection.find({"status": "waiting"}) \
        .sort("queue_number", 1).to_list(length=1000)
    triage_priority = compute_triage_priority(symptom_names)

    queue_size = len(waiting_appts) + 1
    minutes_per_patient = await _get_minutes_per_patient(symptom_names, queue_size)

    insertion_idx = _determine_insertion_index(triage_priority, waiting_appts)
    insertion_pos = insertion_idx + 1
    people_ahead = insertion_pos - 1

    severity = _severity_factor(triage_priority)
    predicted_wait = minutes_per_patient * float(people_ahead) * severity

    # Shift queue numbers
    await collection.update_many(
        {"status": "waiting", "queue_number": {"$gte": insertion_pos}},
        {"$inc": {"queue_number": 1}},
    )

    appointment_doc: Dict[str, Any] = {
        "patient_id": patient_id,
        "symptoms": symptom_names,
        "status": "waiting",
        "queue_number": insertion_pos,
        "predicted_wait_minutes": predicted_wait,
        "triage_priority": triage_priority,
    }
    result = await collection.insert_one(appointment_doc)
    appointment_doc["_id"] = result.inserted_id

    return appointment_doc
