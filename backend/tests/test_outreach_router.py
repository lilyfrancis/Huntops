from unittest.mock import patch

from app.models.enums import SubscriptionTier
from tests.conftest import auth_headers, register_user


def _make_active_job(client, admin_headers, employer_headers, title="Router Test Role", company_name="Acme"):
    resp = client.post(
        "/api/jobs", headers=employer_headers,
        json={
            "title": title, "description": "A description long enough to pass validation.",
            "requirements": ["Python"], "location": "Remote", "job_type": "full_time",
            "experience_level": "mid",
        },
    )
    job = resp.json()
    client.put(f"/api/admin/jobs/{job['id']}/approve", headers=admin_headers)
    return job


def _setup_employer_and_admin(client):
    employer = register_user(client, email="outreach-employer@example.com", role="employer", company_name="Acme")

    from app.db.base import SessionLocal
    from app.models.enums import UserRole
    from app.models.user import User

    admin_data = register_user(client, email="outreach-admin@example.com")
    session = SessionLocal()
    admin_user = session.query(User).filter(User.email == "outreach-admin@example.com").first()
    admin_user.role = UserRole.admin
    employer_user = session.query(User).filter(User.email == "outreach-employer@example.com").first()
    employer_user.is_approved = True
    session.commit()
    session.close()

    admin_login = client.post("/api/auth/login", json={"email": "outreach-admin@example.com", "password": "StrongPass1"})
    return auth_headers(admin_login.json()["access_token"]), auth_headers(employer["access_token"])


def _make_elite_seeker(client, email="outreach-seeker@example.com"):
    data = register_user(client, email=email)
    from app.db.base import SessionLocal
    from app.models.user import User

    session = SessionLocal()
    user = session.query(User).filter(User.email == email).first()
    user.subscription_tier = SubscriptionTier.elite
    user.ai_credits = 100
    session.commit()
    session.close()
    return data


def test_outreach_requires_elite_tier(client):
    admin_headers, employer_headers = _setup_employer_and_admin(client)
    job = _make_active_job(client, admin_headers, employer_headers)

    seeker = register_user(client, email="free-seeker@example.com")  # default free tier
    resp = client.post("/api/outreach", headers=auth_headers(seeker["access_token"]), json={"job_id": job["id"]})
    assert resp.status_code == 403


def test_outreach_404_for_unknown_job(client):
    seeker = _make_elite_seeker(client, "unknownjob@example.com")
    resp = client.post(
        "/api/outreach", headers=auth_headers(seeker["access_token"]),
        json={"job_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@patch("app.services.outreach.outreach_drafting.draft_outreach")
@patch("app.services.outreach.apollo.search_people", return_value=[])
def test_outreach_end_to_end_success_returns_draft(mock_search, mock_draft, client):
    from app.schemas.ai import OutreachDraft

    mock_draft.return_value = OutreachDraft(
        email_subject="Subject", email_body="Body", linkedin_msg="Note", cv_bullets=["Bullet 1"],
    )

    admin_headers, employer_headers = _setup_employer_and_admin(client)
    job = _make_active_job(client, admin_headers, employer_headers, title="E2E Outreach Role")

    seeker = _make_elite_seeker(client, "e2e-seeker@example.com")
    seeker_headers = auth_headers(seeker["access_token"])

    import io
    with patch("app.routers.resumes.resumes_service.parse_resume") as mock_parse:
        from app.schemas.ai import ParsedResume
        mock_parse.return_value = ParsedResume(skills=["Python"], experience_years=4, education="B.Sc.", summary="s", achievements=[])
        client.post("/api/resumes/upload", headers=seeker_headers, files={"file": ("r.txt", io.BytesIO(b"A" * 200), "text/plain")})

    resp = client.post("/api/outreach", headers=seeker_headers, json={"job_id": job["id"]})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft_no_contact"
    assert body["email_subject"] == "Subject"

    mine = client.get("/api/outreach/mine", headers=seeker_headers)
    assert mine.status_code == 200
    assert len(mine.json()) == 1

    detail = client.get(f"/api/outreach/{body['id']}", headers=seeker_headers)
    assert detail.status_code == 200


def test_outreach_requires_resume_first(client):
    admin_headers, employer_headers = _setup_employer_and_admin(client)
    job = _make_active_job(client, admin_headers, employer_headers, title="No Resume Role")
    seeker = _make_elite_seeker(client, "noresume-outreach@example.com")

    resp = client.post("/api/outreach", headers=auth_headers(seeker["access_token"]), json={"job_id": job["id"]})
    assert resp.status_code == 404


def test_other_users_outreach_is_not_visible(client):
    admin_headers, employer_headers = _setup_employer_and_admin(client)
    job = _make_active_job(client, admin_headers, employer_headers, title="Privacy Test Role")

    from app.db.base import SessionLocal
    from app.models.outreach import Outreach
    from app.models.enums import OutreachStatus
    from app.models.user import User

    seeker_a = _make_elite_seeker(client, "privacy-a@example.com")
    seeker_b = _make_elite_seeker(client, "privacy-b@example.com")

    import uuid

    session = SessionLocal()
    user_a = session.query(User).filter(User.email == "privacy-a@example.com").first()
    record = Outreach(user_id=user_a.id, job_id=uuid.UUID(job["id"]), cv_bullets=[], status=OutreachStatus.draft_no_contact)
    session.add(record)
    session.commit()
    record_id = str(record.id)
    session.close()

    resp = client.get(f"/api/outreach/{record_id}", headers=auth_headers(seeker_b["access_token"]))
    assert resp.status_code == 404
