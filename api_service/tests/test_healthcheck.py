from fastapi.testclient import TestClient

def test_middleware_redirects_unauthenticated(client):
    response = client.get("/patient/dashboard", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]

def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text

def test_login_invalid_credentials(client):
    response = client.post("/login", data={
        "email": "doesnotexist@example.com",
        "password": "wrongpassword",
        "role": "patient"
    }, follow_redirects=False)

    assert response.status_code == 302
    assert "/login?error=invalid" in response.headers["location"]

def test_register_patient(client):
    email = "testuser@example.com"

    response = client.post("/register/patient", data={
        "name": "John Test",
        "email": email,
        "password": "secret123"
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/onboarding/symptoms"
    assert "user_id" in response.cookies
    assert response.cookies.get("role") == "patient"

def test_register_patient_duplicate_email(client):
    email = "dupe@example.com"

    client.post("/register/patient", data={
        "name": "Dupe",
        "email": email,
        "password": "pass"
    })

    response = client.post("/register/patient", data={
        "name": "Dupe 2",
        "email": email,
        "password": "pass"
    })

    assert response.status_code == 400
    assert "already registered" in response.text

def test_symptoms_submission(client):
    response = client.post("/register/patient", data={
        "name": "Test User",
        "email": "symptoms@example.com",
        "password": "pass"
    })

    cookies = response.cookies

    response = client.post(
        "/onboarding/symptoms",
        data={"symptoms": ["fever", "cough"]},
        cookies=cookies,
        follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/patient/dashboard"

def test_dashboard_after_login(client):
    response = client.post("/register/patient", data={
        "name": "Dash Test",
        "email": "dash@example.com",
        "password": "pass"
    })

    cookies = response.cookies

    response = client.get("/patient/dashboard", cookies=cookies)
    assert response.status_code == 200
    assert "Dashboard" in response.text
