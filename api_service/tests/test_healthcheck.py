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




