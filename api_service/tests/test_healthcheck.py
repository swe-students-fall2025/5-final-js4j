# def test_middleware_redirects_unauthenticated(client):
#     response = client.get("/patient/dashboard", follow_redirects=False)
#     assert response.status_code in (302, 307)
#     assert "/login" in response.headers["location"]

# def test_login_page_loads(client):
#     response = client.get("/login")
#     assert response.status_code == 200
#     assert "Login" in response.text

# def test_login_invalid_credentials(client):
#     response = client.post("/login", data={
#         "email": "doesnotexist@example.com",
#         "password": "wrongpassword",
#         "role": "patient"
#     }, follow_redirects=False)
#     assert response.status_code == 302
#     assert "/login?error=invalid" in response.headers["location"]

# def test_register_patient(client):
#     email = "testuser@example.com"
#     response = client.post("/register/patient", data={
#         "name": "John Test",
#         "email": email,
#         "password": "secret123"
#     }, follow_redirects=False)

#     assert response.status_code == 302
#     assert response.headers["location"] == "/onboarding/symptoms"
#     assert "user_id" in response.cookies
#     assert response.cookies.get("role") == "patient"

# def test_register_patient_duplicate_email(client):
#     email = "dupe@example.com"
#     client.post("/register/patient", data={
#         "name": "Dupe",
#         "email": email,
#         "password": "pass"
#     })

#     response = client.post("/register/patient", data={
#         "name": "Dupe 2",
#         "email": email,
#         "password": "pass"
#     })

#     assert response.status_code == 400
#     assert "already registered" in response.text

# def test_symptoms_submission(client):
#     response = client.post("/register/patient", data={
#         "name": "Test User",
#         "email": "symptoms@example.com",
#         "password": "pass"
#     })
#     cookies = response.cookies
#     response = client.post(
#         "/onboarding/symptoms",
#         data={"symptoms": ["fever", "cough"]},
#         cookies=cookies,
#         follow_redirects=False
#     )
#     assert response.status_code == 302
#     assert response.headers["location"] == "/patient/dashboard"

# def test_dashboard_after_login(client):
#     response = client.post("/register/patient", data={
#         "name": "Dash Test",
#         "email": "dash@example.com",
#         "password": "pass"
#     })
#     cookies = response.cookies

#     response = client.get("/patient/dashboard", cookies=cookies)
#     assert response.status_code == 200
#     assert "Dashboard" in response.text


# tests/test_healthcheck.py
import pytest
from bson import ObjectId


@pytest.mark.asyncio
async def test_middleware_redirects_unauthenticated(client):
    ac, _ = client
    response = await ac.get("/patient/dashboard", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_login_page_loads(client):
    ac, _ = client
    response = await ac.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    ac, mock_db = client

    # simulate no user found
    mock_db["patients"].find_one.return_value = None

    response = await ac.post(
        "/login",
        data={
            "email": "doesnotexist@example.com",
            "password": "wrongpassword",
            "role": "patient",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login?error=invalid" in response.headers["location"]


@pytest.mark.asyncio
async def test_register_patient(client):
    ac, mock_db = client

    # simulate email not found
    mock_db["patients"].find_one.return_value = None

    new_id = ObjectId()
    mock_db["patients"].insert_one.return_value.inserted_id = new_id

    response = await ac.post(
        "/register/patient",
        data={
            "name": "John Test",
            "email": "testuser@example.com",
            "password": "secret123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/onboarding/symptoms"
    assert response.cookies.get("user_id") == str(new_id)
    assert response.cookies.get("role") == "patient"


@pytest.mark.asyncio
async def test_register_patient_duplicate_email(client):
    ac, mock_db = client

    # simulate duplicate found
    mock_db["patients"].find_one.return_value = {"email": "dupe@example.com"}

    response = await ac.post(
        "/register/patient",
        data={"name": "Dupe", "email": "dupe@example.com", "password": "pass"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "already registered" in response.text


# @pytest.mark.asyncio
# async def test_symptoms_submission(client):
#     ac, mock_db = client

#     # --- Step 1: Register to get cookies ---
#     user_id = ObjectId()
#     mock_db["patients"].find_one.return_value = None
#     mock_db["patients"].insert_one.return_value.inserted_id = user_id

#     register_response = await ac.post(
#         "/register/patient",
#         data={"name": "Test User", "email": "symptoms@example.com", "password": "pass"}
#     )
#     cookies = register_response.cookies

#     # Step 2: Submit symptoms
#     response = await ac.post(
#         "/onboarding/symptoms",
#         data={"symptoms": ["fever", "cough"]},
#         cookies=cookies,
#         follow_redirects=False
#     )

#     assert response.status_code == 302
#     assert response.headers["location"] == "/patient/dashboard"

#     # ensure db update was called
#     mock_db["patients"].update_one.assert_called()


# @pytest.mark.asyncio
# async def test_dashboard_after_login(client):
#     ac, mock_db = client

#     # create fake user id
#     user_id = ObjectId()

#     # Ensure dashboard lookup works
#     mock_db["patients"].find_one.return_value = {"_id": user_id, "name": "Dash", "symptoms": []}

#     response = await ac.get(
#         "/patient/dashboard",
#         cookies={"user_id": str(user_id)}
#     )

#     assert response.status_code == 200
#     assert "Dashboard" in response.text


@pytest.mark.asyncio
async def test_root_redirects_to_login(client):
    ac, _ = client
    res = await ac.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_register_doctor_success(client):
    ac, mock_db = client

    mock_db["doctors"].find_one.return_value = None
    new_id = ObjectId()
    mock_db["doctors"].insert_one.return_value.inserted_id = new_id

    res = await ac.post(
        "/register/doctor",
        data={"name": "Doc", "email": "doc@example.com", "password": "abc123"},
        follow_redirects=False,
    )

    assert res.status_code == 302
    assert res.headers["location"] == "/doctor/dashboard"
    assert res.cookies.get("role") == "doctor"
    assert res.cookies.get("user_id") == str(new_id)


@pytest.mark.asyncio
async def test_register_doctor_duplicate(client):
    ac, mock_db = client

    mock_db["doctors"].find_one.return_value = {"email": "doc@example.com"}

    res = await ac.post(
        "/register/doctor",
        data={"name": "Doc", "email": "doc@example.com", "password": "pass"},
    )

    assert res.status_code == 400
    assert "already registered" in res.text


# @pytest.mark.asyncio
# async def test_symptoms_other_valid(client):
#     ac, mock_db = client
#     user_id = ObjectId()

#     mock_db["patients"].insert_one.return_value.inserted_id = user_id
#     mock_db["patients"].find_one.return_value = None

#     reg = await ac.post("/register/patient", data={
#         "name": "x",
#         "email": "other@example.com",
#         "password": "p"
#     })

#     cookies = reg.cookies

#     res = await ac.post("/onboarding/symptoms", data={
#         "symptoms": ["fever"],
#         "other_symptom": "dizziness"
#     }, cookies=cookies, follow_redirects=False)

#     assert res.status_code == 302
#     mock_db["patients"].update_one.assert_called()
