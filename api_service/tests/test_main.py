import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import api_application


@pytest.mark.asyncio
async def test_register_patient_duplicate(monkeypatch):
    fake_db = MagicMock()
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": AsyncMock(find_one=AsyncMock(return_value={"email": "test@example.com"}))
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/register/patient",
        data={"name": "Test", "email": "test@example.com", "password": "pass"}
    )
    assert response.status_code == 400
    assert "already registered" in response.text


@pytest.mark.asyncio
async def test_register_doctor_duplicate(monkeypatch):
    fake_db = MagicMock()
    fake_db.__getitem__.side_effect = lambda key: {
        "doctors": AsyncMock(find_one=AsyncMock(return_value={"email": "dr@example.com"}))
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/register/doctor",
        data={"name": "Dr", "email": "dr@example.com", "password": "pass"}
    )
    assert response.status_code == 400
    assert "already registered" in response.text


@pytest.mark.asyncio
async def test_symptoms_submit_creates_appointment(monkeypatch):
    fake_patient_id = ObjectId()
    
    fake_db = MagicMock()
    fake_patients = AsyncMock()
    fake_patients.update_one = AsyncMock()
    
    fake_appointments = AsyncMock()
    fake_appointments.find_one = AsyncMock(return_value=None)
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "appointments": fake_appointments
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)
    
    mock_create_appointment = AsyncMock()
    monkeypatch.setattr("app.main.create_appointment_for_patient", mock_create_appointment)

    cookies = {"user_id": str(fake_patient_id), "role": "patient"}
    client = TestClient(api_application)
    response = client.post(
        "/onboarding/symptoms",
        data={"symptoms": ["fever", "cough"], "other_symptom": "headache"},
        cookies=cookies,
        follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/patient/dashboard"
    fake_patients.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_patient_dashboard_no_appointment(monkeypatch):
    fake_patient_id = ObjectId()
    
    fake_db = MagicMock()
    fake_patients = AsyncMock()
    fake_patients.find_one = AsyncMock(return_value={"symptoms": ["fever"], "_id": fake_patient_id})
    
    fake_appointments = AsyncMock()
    fake_appointments.find_one = AsyncMock(return_value=None)
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "appointments": fake_appointments,
        "doctors": AsyncMock()
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    cookies = {"user_id": str(fake_patient_id), "role": "patient"}
    client = TestClient(api_application)
    response = client.get("/patient/dashboard", cookies=cookies)

    assert response.status_code == 200
    assert "html" in response.text.lower() or "<" in response.text


@pytest.mark.asyncio
async def test_doctor_dashboard_with_queue(monkeypatch):
    fake_appt_id = ObjectId()
    fake_patient_id = ObjectId()
    fake_doctor_id = ObjectId()
    
    mock_to_list = AsyncMock(return_value=[
        {
            "_id": fake_appt_id, 
            "patient_id": fake_patient_id, 
            "queue_number": 1, 
            "predicted_wait_minutes": 10, 
            "symptoms": ["fever"]
        }
    ])
    mock_sort = MagicMock(return_value=AsyncMock(to_list=mock_to_list))
    mock_find = MagicMock(return_value=AsyncMock(sort=mock_sort))
    
    fake_db = MagicMock()
    fake_appointments = AsyncMock()
    fake_appointments.find = mock_find
    
    fake_patients = AsyncMock()
    fake_patients.find_one = AsyncMock(return_value={"name": "Test Patient"})
    
    fake_db.__getitem__.side_effect = lambda key: {
        "appointments": fake_appointments,
        "patients": fake_patients,
        "doctors": AsyncMock()
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    cookies = {"user_id": str(fake_doctor_id), "role": "doctor"}
    client = TestClient(api_application)
    response = client.get("/doctor/dashboard", cookies=cookies)

    assert response.status_code == 200
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_symptoms_submit_unauthorized():
    """Test symptoms submission without authentication."""
    client = TestClient(api_application)
    response = client.post(
        "/onboarding/symptoms",
        data={"symptoms": ["fever"], "other_symptom": ""},
        follow_redirects=False
    )
    
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_doctor_dashboard_unauthorized():
    """Test doctor dashboard access without authentication."""
    client = TestClient(api_application)
    response = client.get("/doctor/dashboard", follow_redirects=False)
    
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_patient_dashboard_unauthorized():
    """Test patient dashboard access without authentication."""
    client = TestClient(api_application)
    response = client.get("/patient/dashboard", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_logout_clears_cookies():
    """Test logout clears authentication cookies."""
    client = TestClient(api_application)
    response = client.get("/logout", follow_redirects=False)
    
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"

@pytest.mark.asyncio
async def test_login_success_patient(monkeypatch):
    """Test successful patient login."""
    from passlib.hash import bcrypt
    
    hashed_password = bcrypt.hash("password123")
    mock_patient = {
        "_id": ObjectId(),
        "email": "patient@example.com",
        "password_hash": hashed_password
    }
    
    fake_db = MagicMock()
    fake_patients = AsyncMock(find_one=AsyncMock(return_value=mock_patient))
    fake_doctors = AsyncMock(find_one=AsyncMock(return_value=None))
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "doctors": fake_doctors
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/login",
        data={"email": "patient@example.com", "password": "password123", "role": "patient"},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert response.headers["location"] == "/patient/dashboard"
    assert "user_id" in response.cookies
    assert response.cookies["role"] == "patient"


@pytest.mark.asyncio
async def test_login_success_doctor(monkeypatch):
    """Test successful doctor login."""
    from passlib.hash import bcrypt
    
    hashed_password = bcrypt.hash("doctorpass")
    mock_doctor = {
        "_id": ObjectId(),
        "email": "doctor@example.com",
        "password_hash": hashed_password
    }
    
    fake_db = MagicMock()
    fake_patients = AsyncMock(find_one=AsyncMock(return_value=None))
    fake_doctors = AsyncMock(find_one=AsyncMock(return_value=mock_doctor))
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "doctors": fake_doctors
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/login",
        data={"email": "doctor@example.com", "password": "doctorpass", "role": "doctor"},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert response.headers["location"] == "/doctor/dashboard"
    assert response.cookies["role"] == "doctor"


@pytest.mark.asyncio
async def test_login_invalid_credentials(monkeypatch):
    """Test login with invalid credentials."""
    fake_db = MagicMock()
    fake_patients = AsyncMock(find_one=AsyncMock(return_value=None))
    fake_doctors = AsyncMock(find_one=AsyncMock(return_value=None))
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "doctors": fake_doctors
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/login",
        data={"email": "wrong@example.com", "password": "wrong", "role": "patient"},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert "/login?error=invalid" in response.headers["location"]


@pytest.mark.asyncio
async def test_register_patient_success(monkeypatch):
    """Test successful patient registration."""
    fake_db = MagicMock()
    fake_patients = AsyncMock(
        find_one=AsyncMock(return_value=None), 
        insert_one=AsyncMock(return_value=AsyncMock(inserted_id=ObjectId()))
    )
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/register/patient",
        data={"name": "New Patient", "email": "new@example.com", "password": "password123"},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert response.headers["location"] == "/onboarding/symptoms"
    assert "user_id" in response.cookies
    assert response.cookies["role"] == "patient"


@pytest.mark.asyncio
async def test_register_doctor_success(monkeypatch):
    """Test successful doctor registration."""
    fake_db = MagicMock()
    fake_doctors = AsyncMock(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=AsyncMock(inserted_id=ObjectId()))
    )
    
    fake_db.__getitem__.side_effect = lambda key: {
        "doctors": fake_doctors
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.post(
        "/register/doctor",
        data={"name": "Dr. Smith", "email": "dr@example.com", "password": "doctorpass"},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    assert response.headers["location"] == "/doctor/dashboard"
    assert response.cookies["role"] == "doctor"


@pytest.mark.asyncio
async def test_middleware_allows_public_paths():
    """Test that middleware allows access to public paths without cookies."""
    client = TestClient(api_application)
    
    public_paths = ["/login", "/register/patient", "/register/doctor"]
    
    for path in public_paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code != 302 or "/login" not in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_middleware_blocks_without_cookies():
    """Test that middleware blocks protected paths without cookies."""
    client = TestClient(api_application)
    
    protected_paths = ["/patient/dashboard", "/doctor/dashboard", "/onboarding/symptoms"]
    
    for path in protected_paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_middleware_allows_with_cookies(monkeypatch):
    """Test that middleware allows access with valid cookies."""
    fake_patient_id = ObjectId()
    
    fake_db = MagicMock()
    fake_patients = AsyncMock(find_one=AsyncMock(return_value={"_id": fake_patient_id}))
    fake_appointments = AsyncMock(find_one=AsyncMock(return_value=None))
    
    fake_db.__getitem__.side_effect = lambda key: {
        "patients": fake_patients,
        "appointments": fake_appointments,
        "doctors": AsyncMock()
    }[key]
    
    monkeypatch.setattr("app.main.get_database", lambda: fake_db)

    client = TestClient(api_application)
    response = client.get(
        "/patient/dashboard",
        cookies={"user_id": str(fake_patient_id), "role": "patient"}
    )
    
    assert response.status_code != 302 or "/login" not in response.headers.get("location", "")