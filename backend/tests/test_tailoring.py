"""Tailoring an application to one job.

Auto-apply created applications with cover_letter NULL: the product decided
a role was worth applying to, then sent the weakest possible application.
"""

from unittest.mock import patch

import pytest

from app.models.application import Application
from app.models.application_draft import ApplicationDraft
from app.models.resume import Resume
from app.schemas.ai import TailoredApplication
from app.services import autopilot, tailoring
from app.services.ai_client import AIResponseError
from tests.conftest import auth_headers, register_user
from tests.test_outreach import _elite_user_with_resume, _job

DRAFT = TailoredApplication(
    cover_letter="Hello,\n\nI have run growth at two payments companies.",
    bullets=["Grew pipeline 4.5x in 18 months", "Built the partner channel from zero"],
)


@pytest.fixture
def seeker(db_session):
    from app.core.security import hash_password

    user = _elite_user_with_resume(db_session, email="tailor@example.com", credits=100)
    # The shared helper stores a placeholder hash; these tests log in for real.
    user.password_hash = hash_password("StrongPass1")
    db_session.commit()
    return user


@pytest.fixture
def job(db_session):
    return _job(db_session, title="Head of Growth")


def _generated(value=DRAFT):
    return patch("app.services.tailoring.ai_client.complete_json",
                 return_value=value.model_dump())


# ---------- generating ----------

def test_a_draft_is_written_and_charged_once(db_session, seeker, job):
    before = seeker.ai_credits

    with _generated() as call:
        first = tailoring.generate(db_session, seeker, job)
        second = tailoring.generate(db_session, seeker, job)

    assert first.id == second.id
    assert call.call_count == 1                      # the second read the cache
    db_session.refresh(seeker)
    assert seeker.ai_credits == before - 10          # charged exactly once


def test_regenerating_costs_again_because_it_is_another_call(db_session, seeker, job):
    before = seeker.ai_credits
    with _generated() as call:
        tailoring.generate(db_session, seeker, job)
        tailoring.generate(db_session, seeker, job, force=True)

    assert call.call_count == 2
    db_session.refresh(seeker)
    assert seeker.ai_credits == before - 20


def test_editing_is_free_and_marks_the_draft_as_the_users_own(db_session, seeker, job):
    with _generated():
        draft = tailoring.generate(db_session, seeker, job)
    before = seeker.ai_credits

    tailoring.save_edits(db_session, draft, cover_letter="  My own words.  ",
                         bullets=["  Did a thing  ", "   ", "Did another"])

    db_session.refresh(seeker)
    assert seeker.ai_credits == before
    assert draft.cover_letter == "My own words."
    assert draft.bullets == ["Did a thing", "Did another"]   # blanks dropped
    assert draft.edited is True


def test_a_failed_generation_charges_nothing_and_stores_nothing(db_session, seeker, job):
    before = seeker.ai_credits

    with patch("app.services.tailoring.ai_client.complete_json",
               side_effect=AIResponseError("model unavailable")):
        with pytest.raises(AIResponseError):
            tailoring.generate(db_session, seeker, job)

    db_session.rollback()
    db_session.refresh(seeker)
    assert seeker.ai_credits == before
    assert db_session.query(ApplicationDraft).count() == 0


def test_tailoring_without_a_resume_says_so(db_session, seeker, job):
    db_session.query(Resume).filter(Resume.user_id == seeker.id).delete()
    db_session.commit()

    with pytest.raises(tailoring.NoResumeError):
        tailoring.generate(db_session, seeker, job)


# ---------- through the API ----------

def test_applying_carries_the_draft_without_being_asked(client, db_session, seeker, job):
    """A letter the user wrote and paid for must not be dropped because the
    apply button posted only a job id."""
    with _generated():
        tailoring.generate(db_session, seeker, job)

    token = client.post("/api/auth/login",
                        json={"email": seeker.email, "password": "StrongPass1"}).json()
    headers = auth_headers(token["access_token"])

    resp = client.post("/api/applications", json={"job_id": str(job.id)}, headers=headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["cover_letter"].startswith("Hello,")
    assert body["tailored_bullets"] == DRAFT.bullets


def test_regenerating_over_your_own_edits_is_refused(client, db_session, seeker, job):
    """The one mistake here that cannot be undone."""
    with _generated():
        draft = tailoring.generate(db_session, seeker, job)
    tailoring.save_edits(db_session, draft, cover_letter="Mine.", bullets=[])

    token = client.post("/api/auth/login",
                        json={"email": seeker.email, "password": "StrongPass1"}).json()
    resp = client.post(f"/api/applications/draft/{job.id}?regenerate=true",
                       headers=auth_headers(token["access_token"]))

    assert resp.status_code == 409
    db_session.refresh(draft)
    assert draft.cover_letter == "Mine."


def test_no_credits_is_a_clear_refusal_not_a_failed_draft(client, db_session, seeker, job):
    seeker.ai_credits = 2
    db_session.commit()

    token = client.post("/api/auth/login",
                        json={"email": seeker.email, "password": "StrongPass1"}).json()
    with _generated() as call:
        resp = client.post(f"/api/applications/draft/{job.id}",
                           headers=auth_headers(token["access_token"]))

    assert resp.status_code == 402
    assert "credits" in resp.json()["detail"]
    call.assert_not_called()


# ---------- autopilot ----------

def test_autopilot_applies_with_a_tailored_letter(db_session, seeker, job):
    with _generated():
        assert autopilot._apply(db_session, seeker, job, 92.0) is True
    db_session.commit()

    application = db_session.query(Application).one()
    assert application.cover_letter.startswith("Hello,")
    assert application.tailored_bullets == DRAFT.bullets


def test_autopilot_still_applies_when_tailoring_fails(db_session, seeker, job):
    """Deciding the role is worth applying to is the hard part and it is
    already done. Throwing that away over the easier half would be worse
    than a generic application — but the record has to say which it was."""
    from app.models.autopilot_action import AutopilotAction

    with patch("app.services.tailoring.ai_client.complete_json",
               side_effect=AIResponseError("model unavailable")):
        assert autopilot._apply(db_session, seeker, job, 92.0) is True
    db_session.commit()

    application = db_session.query(Application).one()
    assert application.cover_letter is None

    action = db_session.query(AutopilotAction).one()
    assert "no letter" in action.detail and "drafting failed" in action.detail


def test_autopilot_does_not_tailor_when_credits_are_short(db_session, seeker, job):
    seeker.ai_credits = 1
    db_session.commit()

    with _generated() as call:
        assert autopilot._apply(db_session, seeker, job, 92.0) is True
    db_session.commit()

    call.assert_not_called()
    assert db_session.query(Application).one().cover_letter is None
