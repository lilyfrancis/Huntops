from tests.conftest import auth_headers, register_user


def test_register_grants_signup_credits(client):
    data = register_user(client)
    assert data["user"]["ai_credits"] == 10
    assert data["user"]["subscription_tier"] == "free"
    assert "access_token" in data and "refresh_token" in data


def test_register_rejects_duplicate_email(client):
    register_user(client, email="dupe@example.com")
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "dupe@example.com",
            "password": "StrongPass1",
            "full_name": "Someone Else",
            "role": "job_seeker",
        },
    )
    assert resp.status_code == 400


def test_register_rejects_weak_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "weak", "full_name": "Weak Pw", "role": "job_seeker"},
    )
    assert resp.status_code == 400


def test_register_cannot_self_assign_admin(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "wannabe@example.com", "password": "StrongPass1", "full_name": "X", "role": "admin"},
    )
    assert resp.status_code == 422


def test_login_and_me(client):
    register_user(client, email="login@example.com")
    resp = client.post("/api/auth/login", json={"email": "login@example.com", "password": "StrongPass1"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "login@example.com"


def test_login_wrong_password_rejected(client):
    register_user(client, email="wrongpw@example.com")
    resp = client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "NotThePassword1"})
    assert resp.status_code == 401


def test_refresh_token_issues_new_access_token(client):
    data = register_user(client, email="refresh@example.com")
    resp = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_employer_requires_approval_before_posting_by_default(client):
    data = register_user(client, email="employer@example.com", role="employer", company_name="Acme")
    assert data["user"]["is_approved"] is False

    token = data["access_token"]
    resp = client.post(
        "/api/jobs",
        headers=auth_headers(token),
        json={
            "title": "Senior Engineer",
            "description": "A role description that is long enough to pass validation.",
            "requirements": ["Python"],
            "location": "Remote",
            "job_type": "full_time",
            "experience_level": "senior",
        },
    )
    assert resp.status_code == 403
