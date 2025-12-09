# tests/test_queue_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.services import queue_service


def test_compute_triage_priority():
    symptoms = ["fever", "chest_pain", "unknown"]
    score = queue_service.compute_triage_priority(symptoms)
    assert score == 9.0

    symptoms_empty = []
    assert queue_service.compute_triage_priority(symptoms_empty) == 1.0

    symptoms_high = ["chest_pain"] * 5
    assert queue_service.compute_triage_priority(symptoms_high) <= 10.0


def test_determine_insertion_index():
    appointments = [
        {"triage_priority": 5.0},
        {"triage_priority": 3.0},
        {"triage_priority": 1.0},
    ]
    new_priority = 4.0
    idx = queue_service._determine_insertion_index(new_priority, appointments)
    assert idx == 1 

    new_priority = 6.0
    idx = queue_service._determine_insertion_index(new_priority, appointments)
    assert idx == 0  

    new_priority = 0.5
    idx = queue_service._determine_insertion_index(new_priority, appointments)
    assert idx == len(appointments) 


def test_severity_factor():
    assert queue_service._severity_factor(9.0) == 0.5
    assert queue_service._severity_factor(6.0) == 0.75
    assert queue_service._severity_factor(2.0) == 1.0


@pytest.mark.asyncio
async def test_get_minutes_per_patient():
    mock_ml = AsyncMock(return_value={"predicted_wait_minutes": 20.0})
    
    with patch('app.services.queue_service.request_wait_time_prediction', mock_ml):
        minutes = await queue_service._get_minutes_per_patient(["fever"], queue_size=5)
        assert minutes == 5.0

    mock_ml_zero = AsyncMock(return_value={"predicted_wait_minutes": 0.0})
    
    with patch('app.services.queue_service.request_wait_time_prediction', mock_ml_zero):
        minutes = await queue_service._get_minutes_per_patient(["fever"], queue_size=5)
        assert minutes == 10.0


@pytest.mark.asyncio
async def test_create_appointment_for_patient():
    fake_patient_id = ObjectId()
    fake_inserted_id = ObjectId()
    fake_collection = AsyncMock()
    mock_to_list = AsyncMock(return_value=[])
    mock_sort = MagicMock(return_value=AsyncMock(to_list=mock_to_list))
    mock_find = MagicMock(return_value=AsyncMock(sort=mock_sort))
    fake_collection.find = mock_find
    
    fake_collection.insert_one = AsyncMock(return_value=AsyncMock(inserted_id=fake_inserted_id))
    fake_collection.find_one = AsyncMock(return_value={"_id": fake_inserted_id})
    fake_collection.update_many = AsyncMock()
    fake_db = MagicMock()
    fake_db.__getitem__.return_value = fake_collection
    
    with patch('app.services.queue_service.get_database', return_value=fake_db):
        mock_recalculate = AsyncMock()
        with patch('app.services.queue_service.recalculate_wait_times_for_waiting_appointments', mock_recalculate):
            result = await queue_service.create_appointment_for_patient(
                fake_patient_id, 
                ["fever"]
            )

    assert result["_id"] == fake_inserted_id
    fake_collection.insert_one.assert_awaited_once()
    fake_collection.update_many.assert_awaited_once()
    mock_recalculate.assert_awaited_once()


@pytest.mark.asyncio
async def test_recalculate_wait_times_for_waiting_appointments():
    fake_appointments = [
        {"_id": ObjectId(), "symptoms": ["fever"], "triage_priority": 5.0},
        {"_id": ObjectId(), "symptoms": ["chest_pain"], "triage_priority": 9.0},
    ]
    fake_collection = AsyncMock()
    mock_to_list = AsyncMock(return_value=fake_appointments)
    mock_sort = MagicMock(return_value=AsyncMock(to_list=mock_to_list))
    mock_find = MagicMock(return_value=AsyncMock(sort=mock_sort))
    fake_collection.find = mock_find
    
    fake_collection.update_one = AsyncMock()
    fake_db = MagicMock()
    fake_db.__getitem__.return_value = fake_collection
    
    with patch('app.services.queue_service.get_database', return_value=fake_db):
        mock_get_minutes = AsyncMock(return_value=10.0)
        with patch('app.services.queue_service._get_minutes_per_patient', mock_get_minutes):
            await queue_service.recalculate_wait_times_for_waiting_appointments()
    
    assert fake_collection.update_one.await_count == 2


@pytest.mark.asyncio
async def test_create_appointment_for_patient_with_existing_queue():
    """Test creating appointment when there are existing appointments."""
    fake_patient_id = ObjectId()
    fake_inserted_id = ObjectId()

    existing_appointments = [
        {"_id": ObjectId(), "symptoms": ["fever"], "triage_priority": 3.0, "queue_number": 1},
        {"_id": ObjectId(), "symptoms": ["cough"], "triage_priority": 1.0, "queue_number": 2},
    ]

    fake_collection = AsyncMock()
    
    mock_to_list = AsyncMock(return_value=existing_appointments)
    mock_sort = MagicMock(return_value=AsyncMock(to_list=mock_to_list))
    mock_find = MagicMock(return_value=AsyncMock(sort=mock_sort))
    fake_collection.find = mock_find
    
    fake_collection.insert_one = AsyncMock(return_value=AsyncMock(inserted_id=fake_inserted_id))
    fake_collection.find_one = AsyncMock(return_value={
        "_id": fake_inserted_id,
        "patient_id": fake_patient_id,
        "symptoms": ["chest_pain"], 
        "queue_number": 1
    })
    fake_collection.update_many = AsyncMock()

    fake_db = MagicMock()
    fake_db.__getitem__.return_value = fake_collection
    
    with patch('app.services.queue_service.get_database', return_value=fake_db):
        mock_recalculate = AsyncMock()
        with patch('app.services.queue_service.recalculate_wait_times_for_waiting_appointments', mock_recalculate):
            result = await queue_service.create_appointment_for_patient(
                fake_patient_id, 
                ["chest_pain"]
            )

    fake_collection.update_many.assert_awaited_once_with(
        {"status": "waiting", "queue_number": {"$gte": 1}},
        {"$inc": {"queue_number": 1}}
    )
    assert result["queue_number"] == 1


@pytest.mark.asyncio
async def test_recalculate_wait_times_empty_queue():
    """Test recalculating wait times when queue is empty."""
    fake_collection = AsyncMock()
    
    mock_to_list = AsyncMock(return_value=[])
    mock_sort = MagicMock(return_value=AsyncMock(to_list=mock_to_list))
    mock_find = MagicMock(return_value=AsyncMock(sort=mock_sort))
    fake_collection.find = mock_find
    
    fake_db = MagicMock()
    fake_db.__getitem__.return_value = fake_collection
    
    with patch('app.services.queue_service.get_database', return_value=fake_db):
        await queue_service.recalculate_wait_times_for_waiting_appointments()
    
    fake_collection.update_one.assert_not_awaited()


def test_compute_triage_priority_duplicate_symptoms():
    """Test that duplicate symptoms don't double-count."""
    symptoms = ["fever", "fever", "fever", "chest_pain", "chest_pain"]
    score = queue_service.compute_triage_priority(symptoms)
    assert score == 8.0


def test_compute_triage_priority_case_sensitivity():
    """Test that symptom names are case-insensitive."""
    symptoms = ["FEVER", "Chest_Pain", "cough"]
    score = queue_service.compute_triage_priority(symptoms)
    assert score == 9.0  # 3.0 + 5.0 + 1.0 = 9.0


@pytest.mark.asyncio
async def test_get_minutes_per_patient_key_error():
    """Test when ML response doesn't have expected key."""
    mock_ml = AsyncMock(return_value={"wrong_key": 20.0})
    
    with patch('app.services.queue_service.request_wait_time_prediction', mock_ml):
        minutes = await queue_service._get_minutes_per_patient(["fever"], queue_size=3)
        assert minutes == 10.0


@pytest.mark.asyncio
async def test_get_minutes_per_patient_queue_size_one():
    """Test with queue_size = 1."""
    mock_ml = AsyncMock(return_value={"predicted_wait_minutes": 15.0})
    
    with patch('app.services.queue_service.request_wait_time_prediction', mock_ml):
        minutes = await queue_service._get_minutes_per_patient(["fever"], queue_size=1)
        assert minutes == 15.0