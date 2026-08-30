from tests.conftest import auth_headers, register_user

JOB_PAYLOAD = {
    "title": "Senior RevOps Lead",
    "description": "A role description that is long enough to pass validation checks.",
    "requirements": ["Salesforce", "HubSpot", "Automation"],
    "location": "Remote",
    "job_type": "full_time",
    "experience_level": "senior",
}


def _approved_employer(client, email="employer@example.com"):
    data = register_user(client, email=email, role="employer", company_name="Acme")
    token = data["access_token"]
    # Simulate admin approval directly via an admin account rather than the
    # (deliberately absent) self-serve endpoint.
    admin = register_user(client, email="admin@example.com", role="job_seeker")
    return data, token


def _admin_headers(client):
    # There is no public admin self-registration; promote via direct model
    # access in this test helper only.
    from app.db.base import SessionLocal
    from app.models.enums import UserRole
    from app.models.user import User

    session = SessionLocal()
    admin = session.query(User).filter(User.email == "admin@example.com").first()
    admin.role = UserRole.admin
    session.commit()
    session.close()

    resp = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "StrongPass1"})
    return auth_headers(resp.json()["access_token"])


def test_employer_job_lifecycle_requires_admin_approval(client):
    employer_data, employer_token = _approved_employer(client)
    admin_headers = _admin_headers(client)

    # Approve the employer account itself first.
    approve_resp = client.put(
        f"/api/admin/users/{employer_data['user']['id']}/approve", headers=admin_headers
    )
    assert approve_resp.status_code == 200

    create_resp = client.post("/api/jobs", headers=auth_headers(employer_token), json=JOB_PAYLOAD)
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["status"] == "pending"

    # Not visible in the public feed yet.
    listing = client.get("/api/jobs").json()
    assert all(j["id"] != job["id"] for j in listing)

    approve_job = client.put(f"/api/admin/jobs/{job['id']}/approve", headers=admin_headers)
    assert approve_job.status_code == 200
    assert approve_job.json()["status"] == "active"

    listing = client.get("/api/jobs").json()
    assert any(j["id"] == job["id"] for j in listing)


def test_job_seeker_can_apply_once(client):
    employer_data, employer_token = _approved_employer(client, email="employer2@example.com")
    admin_headers = _admin_headers(client)
    client.put(f"/api/admin/users/{employer_data['user']['id']}/approve", headers=admin_headers)

    job = client.post("/api/jobs", headers=auth_headers(employer_token), json=JOB_PAYLOAD).json()
    client.put(f"/api/admin/jobs/{job['id']}/approve", headers=admin_headers)

    seeker = register_user(client, email="seeker2@example.com")
    seeker_headers = auth_headers(seeker["access_token"])

    first = client.post("/api/applications", headers=seeker_headers, json={"job_id": job["id"]})
    assert first.status_code == 201

    duplicate = client.post("/api/applications", headers=seeker_headers, json={"job_id": job["id"]})
    assert duplicate.status_code == 400

    mine = client.get("/api/applications/mine", headers=seeker_headers)
    assert len(mine.json()) == 1

    employer_view = client.get(f"/api/applications/job/{job['id']}", headers=auth_headers(employer_token))
    assert employer_view.status_code == 200
    assert len(employer_view.json()) == 1


def test_only_owning_employer_can_see_applications(client):
    employer_data, employer_token = _approved_employer(client, email="employer3@example.com")
    admin_headers = _admin_headers(client)
    client.put(f"/api/admin/users/{employer_data['user']['id']}/approve", headers=admin_headers)

    job = client.post("/api/jobs", headers=auth_headers(employer_token), json=JOB_PAYLOAD).json()
    client.put(f"/api/admin/jobs/{job['id']}/approve", headers=admin_headers)

    other_employer = register_user(client, email="other-employer@example.com", role="employer", company_name="Other")
    resp = client.get(f"/api/applications/job/{job['id']}", headers=auth_headers(other_employer["access_token"]))
    assert resp.status_code == 403


def test_job_seeker_cannot_post_jobs(client):
    seeker = register_user(client, email="notemployer@example.com")
    resp = client.post("/api/jobs", headers=auth_headers(seeker["access_token"]), json=JOB_PAYLOAD)
    assert resp.status_code == 403
