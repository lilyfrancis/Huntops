"""The product with no credit on the provider account.

The parts that earn money — signing up, browsing, unlocking a listing,
applying — never needed an AI call, and must not start needing one just
because a different part of the product does. Otherwise an empty provider
balance stops the very revenue that would refill it.

This pins the whole path end to end, with every AI call failing.
"""

import io
import uuid
from unittest.mock import patch

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.user import User
from app.services.ai_client import AIResponseError
from tests.conftest import register_user


def _job(db, title="Senior Backend Engineer", source="remotive") -> Job:
    job = Job(
        title=title, description="d" * 200, requirements=["Python"], location="Lagos, Nigeria",
        job_type=JobType.full_time, experience_level=ExperienceLevel.senior, source=source,
        source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active,
        company_name="Paystack",
    )
    db.add(job)
    db.commit()
    return job


def _headers(client, email):
    data = register_user(client, email=email)
    return {"Authorization": f"Bearer {data['access_token']}"}, uuid.UUID(data["user"]["id"])


def test_a_new_user_can_sign_up_browse_and_upload_with_every_ai_call_failing(client, db_session):
    _job(db_session)
    headers, _ = _headers(client, "nocredit@example.com")

    feed = client.get("/api/jobs/feed", headers=headers)
    assert feed.status_code == 200
    assert len(feed.json()) == 1

    with patch(
        "app.routers.resumes.resumes_service.parse_resume",
        side_effect=AIResponseError("credit balance too low"),
    ):
        upload = client.post(
            "/api/resumes/upload",
            headers=headers,
            files={"file": ("cv.txt", io.BytesIO(b"A" * 300), "text/plain")},
        )

    assert upload.status_code == 201, upload.text
    assert upload.json()["parse_status"] == "pending"


def test_the_feed_shows_a_locked_listing_without_giving_it_away(client, db_session):
    """"See half the jobs until they pay" is the existing model, and it has
    to hold with no AI: enough of the title to want it, no company and no
    link to route around us with."""
    _job(db_session, title="Senior Backend Engineer")
    headers, _ = _headers(client, "locked@example.com")

    item = client.get("/api/jobs/feed", headers=headers).json()[0]["job"]

    assert item["title"].startswith("Senior Backend")
    assert "Engineer" not in item["title"]
    assert item["company_name"] is None
    assert item["source_url"] is None
    # Enough to judge it by.
    assert item["location"] == "Lagos, Nigeria"


def test_unlocking_a_listing_costs_credits_and_no_ai_call(client, db_session):
    """The transaction that funds the provider account. If this needed the
    provider, an empty balance would be self-sealing."""
    from app.db.base import SessionLocal

    job = _job(db_session)
    headers, user_id = _headers(client, "buyer@example.com")

    session = SessionLocal()
    try:
        session.get(User, user_id).credits = 50
        session.commit()
    finally:
        session.close()

    with patch("app.services.ai_client.complete_json", side_effect=AssertionError("no AI here")):
        resp = client.post(f"/api/jobs/{job.id}/unlock", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["company_name"] == "Paystack"
    assert resp.json()["source_url"] is not None


def test_applying_needs_no_ai_call(client, db_session):
    from app.db.base import SessionLocal

    job = _job(db_session, source="internal")
    headers, user_id = _headers(client, "applicant@example.com")

    session = SessionLocal()
    try:
        session.get(User, user_id).credits = 50
        session.commit()
    finally:
        session.close()

    with patch("app.services.ai_client.complete_json", side_effect=AssertionError("no AI here")):
        resp = client.post("/api/applications", headers=headers, json={"job_id": str(job.id)})

    assert resp.status_code in (200, 201), resp.text


def test_a_pending_cv_is_read_once_the_provider_answers_again(db_session):
    """The other half of accepting an unparsed upload: it has to be caught
    up, or a user who signed up during an outage never gets matches."""
    from app.models.resume import Resume
    from app.schemas.ai import ParsedResume
    from app.scripts.parse_pending_resumes import parse_pending

    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    db_session.add(Resume(
        user_id=user.id, raw_text="A" * 300, parse_status="pending", label="CV",
    ))
    db_session.commit()

    with patch(
        "app.services.resumes.parse_resume",
        return_value=ParsedResume(skills=["Python"], experience_years=5,
                                  education="BSc", summary="s", achievements=[]),
    ):
        summary = parse_pending()

    assert summary["parsed"] == 1
    assert summary["still_pending"] == 0
    assert db_session.query(Resume).filter(Resume.user_id == user.id).one().parsed_skills == ["Python"]


def test_the_catch_up_stops_at_the_first_failure(db_session):
    """Still out of credit means the next two hundred calls fail the same
    way at the same price."""
    from app.models.resume import Resume
    from app.scripts.parse_pending_resumes import parse_pending

    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    for _ in range(5):
        db_session.add(Resume(user_id=user.id, raw_text="A" * 300, parse_status="pending", label="CV"))
    db_session.commit()

    calls = []

    def fail(text):
        calls.append(1)
        raise AIResponseError("credit balance too low")

    with patch("app.services.resumes.parse_resume", side_effect=fail):
        summary = parse_pending()

    assert len(calls) == 1
    assert summary["parsed"] == 0
    assert summary["still_pending"] == 5
