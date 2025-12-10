"""Queue service for managing patient appointments and computing triage priorities."""

from typing import List, Dict, Any
from datetime import datetime

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

READY_FOR_APPOINTMENT_MESSAGE = "Hi! We are ready for your appointment now!"


def compute_triage_priority(symptom_names: List[str]) -> float:
    """Compute a deterministic triage score based solely on symptoms."""
    score = sum(
        (
            5.0
            if s.lower() in VERY_URGENT_SYMPTOMS
            else 3.0 if s.lower() in MEDIUM_URGENT_SYMPTOMS else 1.0
        )
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


def _determine_insertion_index(
    new_priority: float, appointments: List[Dict[str, Any]]
) -> int:
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
    database = get_database()
    collection = database["appointments"]

    waiting_appointments = (
        await collection.find({"status": "waiting"})
        .sort("queue_number", 1)
        .to_list(length=1000)
    )
    triage_priority = compute_triage_priority(symptom_names)

    insertion_index = _determine_insertion_index(triage_priority, waiting_appointments)
    insertion_position = insertion_index + 1

    # Shift queue numbers for everyone at or after the insertion point
    await collection.update_many(
        {"status": "waiting", "queue_number": {"$gte": insertion_position}},
        {"$inc": {"queue_number": 1}},
    )

    appointment_document: Dict[str, Any] = {
        "patient_id": patient_id,
        "symptoms": symptom_names,
        "status": "waiting",
        "queue_number": insertion_position,
        # Temporary value; will be recalculated for everyone below
        "predicted_wait_minutes": 0.0,
        "triage_priority": triage_priority,
        "created_at": datetime.utcnow(),
    }
    insertion_result = await collection.insert_one(appointment_document)
    inserted_id = insertion_result.inserted_id

    # Recalculate ETAs for all waiting patients (including the new one)
    await recalculate_wait_times_for_waiting_appointments()

    updated_document = await collection.find_one({"_id": inserted_id})
    return updated_document


async def recalculate_wait_times_for_waiting_appointments() -> None:
    """Recalculate predicted_wait_minutes for all waiting patients based on queue order."""
    database = get_database()
    collection = database["appointments"]

    waiting_appointments = (
        await collection.find({"status": "waiting"})
        .sort("queue_number", 1)
        .to_list(length=1000)
    )

    if not waiting_appointments:
        return

    queue_length = len(waiting_appointments)

    for index_in_queue, appointment_document in enumerate(waiting_appointments):
        symptom_names = appointment_document.get("symptoms", [])
        triage_priority = appointment_document.get("triage_priority")

        if triage_priority is None:
            triage_priority = compute_triage_priority(symptom_names)

        # Use the ML service to estimate minutes per patient for this queue
        minutes_per_patient = await _get_minutes_per_patient(
            symptom_names=symptom_names,
            queue_size=queue_length,
        )

        people_ahead = index_in_queue  # 0 for first in queue
        severity = _severity_factor(triage_priority)
        predicted_wait = minutes_per_patient * float(people_ahead) * severity

        await collection.update_one(
            {"_id": appointment_document["_id"]},
            {
                "$set": {
                    "queue_number": index_in_queue + 1,
                    "triage_priority": triage_priority,
                    "predicted_wait_minutes": predicted_wait,
                }
            },
        )


async def notify_next_patient_ready(
    doctor_identifier: ObjectId | None = None,
) -> Dict[str, Any] | None:
    """Create a 'ready for appointment' message for the next waiting patient."""
    database = get_database()
    appointments_collection = database["appointments"]
    messages_collection = database["messages"]

    # Find the next patient in the queue: the waiting appointment with smallest queue_number
    next_appointment_document = await appointments_collection.find_one(
        {"status": "waiting"},
        sort=[("queue_number", 1)],
    )

    if not next_appointment_document:
        return None

    message_document: Dict[str, Any] = {
        "patient_id": next_appointment_document["patient_id"],
        "doctor_id": doctor_identifier,
        "appointment_id": next_appointment_document["_id"],
        "text": READY_FOR_APPOINTMENT_MESSAGE,
        "created_at": datetime.utcnow(),
        "read": False,
        "kind": "ready_for_appointment",
    }

    insert_result = await messages_collection.insert_one(message_document)

    return {
        "patient_id": str(next_appointment_document["patient_id"]),
        "message_id": str(insert_result.inserted_id),
    }
