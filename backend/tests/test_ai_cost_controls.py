"""The four changes that stop the API bill growing with sign-ups.

Each one guards a leak that cost real money and was invisible: work paid for
twice, work paid for on behalf of people who were not there, and an unbounded
document sent to a model on every alert email.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.core.config import get_settings
from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import JobFitScore
from app.services import email_extraction, matching, scheduler

settings = get_settings()


def _user(db, **kw) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker", **kw)
    db.add(user)
    db.flush()
    return user


def _job(db, title="A role") -> Job:
    job = Job(title=title, description="d" * 300, requirements=["x"], location="Lagos, Nigeria",
              job_type=JobType.full_time, experience_level=ExperienceLevel.senior,
              source="internal", source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active)
    db.add(job)
    db.flush()
    return job


def _score(value: float) -> JobFitScore:
    return JobFitScore(job_index=0, overall_score=value, skills_score=value,
                       experience_score=value, location_score=value, reason="r")


# ---------- 1. the usage log ----------

def test_every_call_logs_what_it_spent_and_on_what(caplog):
    """Without this the only record is one total in the provider's console,
    and "scoring is expensive" cannot be told from "reading the alert emails
    is expensive" — which decides which change is worth making."""
    from app.services import ai_client

    fake = MagicMock()
    fake.content = [MagicMock(text='{"ok": true}')]
    fake.stop_reason = "end_turn"
    fake.usage = MagicMock(input_tokens=1234, output_tokens=56)
    client = MagicMock()
    client.messages.create.return_value = fake

    with patch.object(ai_client, "_get_client", return_value=client):
        with caplog.at_level(logging.INFO):
            ai_client.complete_json(system="s", prompt="p", model="m", feature="scoring")

    line = next(r.getMessage() for r in caplog.records if "ai.usage" in r.getMessage())
    assert "feature=scoring" in line
    assert "in=1234" in line
    assert "out=56" in line


# ---------- 2. the unbounded email ----------

def test_a_long_alert_email_is_trimmed_before_it_is_sent(monkeypatch):
    """The whole body used to go, every time. A stripped LinkedIn digest runs
    to tens of thousands of characters, nearly all of it footer."""
    monkeypatch.setattr(settings, "MAX_EXTRACTION_CHARS", 500)
    sent = {}

    def fake_complete(system, prompt, model, max_tokens, feature="unknown"):
        sent["prompt"] = prompt
        return []

    monkeypatch.setattr(email_extraction.ai_client, "complete_json", fake_complete)
    email_extraction.extract_jobs_from_email("JOB LISTINGS" + ("x" * 40_000))

    assert len(sent["prompt"]) < 2_000


def test_a_short_email_is_sent_whole(monkeypatch):
    monkeypatch.setattr(settings, "MAX_EXTRACTION_CHARS", 14_000)
    sent = {}

    def fake_complete(system, prompt, model, max_tokens, feature="unknown"):
        sent["prompt"] = prompt
        return []

    monkeypatch.setattr(email_extraction.ai_client, "complete_json", fake_complete)
    email_extraction.extract_jobs_from_email("Head of Growth at Paystack, Lagos")

    assert "Head of Growth at Paystack" in sent["prompt"]


# ---------- 3. never paying for the same job twice ----------

def test_a_rejected_job_is_remembered_so_it_is_not_scored_again(db_session):
    """The leak that compounded. A job sits in the newest-forty window for
    days; with no record of the rejection it was rejected again every
    morning, at full price."""
    user = _user(db_session)
    job = _job(db_session)

    matching.persist_matches(db_session, user, [(job, _score(30), False)])
    db_session.flush()

    assert db_session.query(JobMatch).filter(JobMatch.user_id == user.id).count() == 1


def test_persist_returns_only_what_cleared_the_bar(db_session):
    user = _user(db_session)
    good, bad = _job(db_session, "Good"), _job(db_session, "Bad")

    returned = matching.persist_matches(
        db_session, user, [(good, _score(80), False), (bad, _score(30), False)]
    )

    assert [job.title for _m, job in returned] == ["Good"]


def test_an_already_scored_job_is_not_a_candidate_again(db_session):
    user = _user(db_session)
    scored, fresh = _job(db_session, "Scored"), _job(db_session, "Fresh")
    matching.persist_matches(db_session, user, [(scored, _score(30), False)])
    db_session.flush()

    candidates = matching.unscored_for(db_session, user, db_session.query(Job), limit=10)

    assert [j.title for j in candidates] == ["Fresh"]


def test_with_nothing_new_there_is_nothing_to_score(db_session):
    user = _user(db_session)
    job = _job(db_session)
    matching.persist_matches(db_session, user, [(job, _score(80), False)])
    db_session.flush()

    assert matching.unscored_for(db_session, user, db_session.query(Job), limit=10) == []


# ---------- 4. not paying on behalf of people who left ----------

def test_an_account_dormant_past_the_window_is_skipped(db_session):
    user = _user(db_session, last_seen_at=datetime.now(timezone.utc) - timedelta(days=60))

    assert scheduler._is_dormant(user) is True


def test_an_account_seen_recently_is_not(db_session):
    user = _user(db_session, last_seen_at=datetime.now(timezone.utc) - timedelta(days=2))

    assert scheduler._is_dormant(user) is False


def test_an_account_that_predates_the_column_counts_as_active(db_session):
    """Null means the column arrived after they did. Skipping somebody
    because of when a migration ran would be the wrong kind of saving."""
    assert scheduler._is_dormant(_user(db_session, last_seen_at=None)) is False


def test_the_check_can_be_switched_off(db_session, monkeypatch):
    monkeypatch.setattr(settings, "DIGEST_DORMANT_AFTER_DAYS", 0)
    user = _user(db_session, last_seen_at=datetime.now(timezone.utc) - timedelta(days=400))

    assert scheduler._is_dormant(user) is False


def test_signing_in_records_the_visit(client):
    from app.db.base import SessionLocal
    from tests.conftest import register_user

    data = register_user(client, email="seen@example.com")
    resp = client.post("/api/auth/login", json={"email": "seen@example.com", "password": "StrongPass1"})

    assert resp.status_code == 200
    session = SessionLocal()
    try:
        user = session.get(User, uuid.UUID(data["user"]["id"]))
        assert user.last_seen_at is not None
    finally:
        session.close()
