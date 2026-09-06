"""Autopilot: acting in someone's name, within the limits they set."""

from types import SimpleNamespace
from unittest.mock import patch

from app.models.application import Application
from app.models.autopilot_action import AutopilotAction
from app.models.enums import ExperienceLevel, JobStatus, JobType, OutreachStatus, SubscriptionTier, UserRole
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services import autopilot
from app.services import outreach as outreach_service
from tests.conftest import auth_headers, register_user


def _seeker(session, email="pilot@example.com", **pref_kwargs):
    user = User(
        email=email, password_hash="x", full_name="Pilot User", role=UserRole.job_seeker,
        subscription_tier=SubscriptionTier.elite, ai_credits=500,
    )
    session.add(user)
    session.flush()
    session.add(UserPreference(user_id=user.id, **pref_kwargs))
    session.commit()
    session.refresh(user)
    return user


def _job(session, *, title, source="internal", score=None, user=None, ghost_score=None):
    job = Job(
        title=title, description="d", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid, status=JobStatus.active,
        source=source, source_url=f"https://example.com/{title.replace(' ', '-')}",
        company_name="Acme", ghost_score=ghost_score,
    )
    session.add(job)
    session.flush()
    if score is not None:
        session.add(JobMatch(user_id=user.id, job_id=job.id, fit_score=score))
    session.commit()
    session.refresh(job)
    return job


# ---------- the switches ----------

def test_autopilot_does_nothing_when_both_switches_are_off(db_session):
    user = _seeker(db_session)
    _job(db_session, title="Great Role", score=99, user=user)

    assert autopilot.run_for_user(db_session, user) == {
        "applied": 0, "outreach": 0, "skipped": 0, "failed": 0, "capped": False
    }
    assert db_session.query(Application).count() == 0


def test_auto_apply_submits_internal_jobs_above_the_threshold(db_session):
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=85)
    job = _job(db_session, title="Strong Internal Role", score=92, user=user)

    summary = autopilot.run_for_user(db_session, user)

    assert summary["applied"] == 1
    application = db_session.query(Application).one()
    assert application.job_id == job.id
    db_session.refresh(job)
    assert job.application_count == 1

    action = db_session.query(AutopilotAction).one()
    assert (action.action, action.status) == ("apply", "done")
    assert action.fit_score == 92


def test_auto_apply_leaves_jobs_below_the_threshold_alone(db_session):
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=90)
    _job(db_session, title="Mediocre Role", score=88, user=user)

    assert autopilot.run_for_user(db_session, user)["applied"] == 0
    assert db_session.query(Application).count() == 0


def test_auto_apply_never_touches_external_jobs(db_session):
    """An aggregated listing lives behind someone else's form; we cannot
    submit it. Auto-apply silently 'applying' would be a fabricated record."""
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    _job(db_session, title="External Role", source="remotive", score=99, user=user)

    assert autopilot.run_for_user(db_session, user)["applied"] == 0
    assert db_session.query(Application).count() == 0


def test_auto_outreach_handles_external_jobs(db_session):
    user = _seeker(db_session, autopilot_outreach_enabled=True, autopilot_outreach_threshold=90)
    job = _job(db_session, title="External Role", source="remotive", score=95, user=user)

    sent = SimpleNamespace(status=OutreachStatus.sent)
    with patch("app.services.autopilot.outreach_service.initiate_outreach", return_value=sent) as mock_outreach:
        summary = autopilot.run_for_user(db_session, user)

    assert summary["outreach"] == 1
    mock_outreach.assert_called_once()
    assert mock_outreach.call_args[0][2].id == job.id
    assert db_session.query(AutopilotAction).one().action == "outreach"


def test_auto_outreach_does_not_apply_to_internal_jobs(db_session):
    user = _seeker(db_session, autopilot_outreach_enabled=True, autopilot_outreach_threshold=80)
    _job(db_session, title="Internal Role", source="internal", score=99, user=user)

    with patch("app.services.autopilot.outreach_service.initiate_outreach") as mock_outreach:
        summary = autopilot.run_for_user(db_session, user)

    mock_outreach.assert_not_called()
    assert summary == {"applied": 0, "outreach": 0, "skipped": 0, "failed": 0, "capped": False}


# ---------- the guardrails ----------

def test_the_daily_cap_bounds_how_much_it_can_do(db_session):
    """The failure this exists for: a bad scoring day firing fifty
    applications in someone's name before they notice."""
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80, autopilot_daily_cap=2)
    for i in range(5):
        _job(db_session, title=f"Role {i}", score=95, user=user)

    summary = autopilot.run_for_user(db_session, user)

    assert summary["applied"] == 2
    assert summary["capped"] is True
    assert db_session.query(Application).count() == 2


def test_a_second_run_the_same_day_respects_the_cap_already_spent(db_session):
    """Otherwise the manual "run now" button is a way to bypass the cap by
    clicking repeatedly."""
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80, autopilot_daily_cap=2)
    for i in range(5):
        _job(db_session, title=f"Role {i}", score=95, user=user)

    autopilot.run_for_user(db_session, user)
    second = autopilot.run_for_user(db_session, user)

    assert second["applied"] == 0
    assert second["capped"] is True
    assert db_session.query(Application).count() == 2


def test_a_job_is_never_acted_on_twice(db_session):
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80, autopilot_daily_cap=10)
    _job(db_session, title="Only Role", score=95, user=user)

    autopilot.run_for_user(db_session, user)
    autopilot.run_for_user(db_session, user)

    assert db_session.query(Application).count() == 1
    assert db_session.query(AutopilotAction).count() == 1


def test_a_declined_job_is_not_reconsidered(db_session):
    """Skips are remembered too. Re-deciding a job every night means the day a
    score drifts a point it fires on something already shown as out of scope."""
    user = _seeker(db_session, autopilot_outreach_enabled=True, autopilot_outreach_threshold=80)
    _job(db_session, title="External Role", source="remotive", score=95, user=user)

    with patch(
        "app.services.autopilot.outreach_service.initiate_outreach",
        side_effect=outreach_service.InsufficientCreditsError("Need 30 credits, have 0"),
    ) as mock_outreach:
        first = autopilot.run_for_user(db_session, user)
        second = autopilot.run_for_user(db_session, user)

    assert first["skipped"] == 1
    assert second["skipped"] == 0
    assert mock_outreach.call_count == 1

    action = db_session.query(AutopilotAction).one()
    assert action.status == "skipped"
    assert "credits" in action.detail


def test_autopilot_will_not_apply_to_a_flagged_ghost(db_session):
    """It runs through the same preference-filtered feed the user sees, and
    that feed hides flagged ghosts."""
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    _job(db_session, title="Probably Fake", score=99, user=user, ghost_score=95)

    assert autopilot.run_for_user(db_session, user)["applied"] == 0
    assert db_session.query(Application).count() == 0


def test_autopilot_stays_inside_the_users_preference_filter(db_session):
    """It must never act on a job the user would not have been shown."""
    user = _seeker(
        db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80,
        target_markets=["Canada"],
    )
    job = _job(db_session, title="UK Role", score=99, user=user)
    job.market = "UK"
    db_session.commit()

    assert autopilot.run_for_user(db_session, user)["applied"] == 0


def test_a_manual_application_in_the_meantime_is_not_a_failure(db_session):
    user = _seeker(db_session, autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    job = _job(db_session, title="Raced Role", score=95, user=user)
    db_session.add(Application(
        job_id=job.id, candidate_id=user.id, candidate_name=user.full_name, candidate_email=user.email
    ))
    db_session.commit()

    summary = autopilot.run_for_user(db_session, user)

    assert summary["applied"] == 0
    assert summary["skipped"] == 1
    assert db_session.query(Application).count() == 1
    assert "manually" in db_session.query(AutopilotAction).one().detail


def test_run_all_skips_users_who_never_enabled_it(db_session):
    _seeker(db_session, email="off@example.com")
    on = _seeker(db_session, email="on@example.com", autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    _job(db_session, title="Shared Role", score=95, user=on)

    totals = autopilot.run_all(db_session)

    assert totals["users"] == 1
    assert totals["applied"] == 1


def test_run_all_survives_one_users_failure(db_session):
    """One user's bad state must not stop everyone else's run."""
    broken = _seeker(db_session, email="broken@example.com", autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    _job(db_session, title="Role A", score=95, user=broken)

    real_run = autopilot.run_for_user

    def _explode_for_broken(db, user):
        if user.email == "broken@example.com":
            raise RuntimeError("something went wrong")
        return real_run(db, user)

    healthy = _seeker(db_session, email="healthy@example.com", autopilot_apply_enabled=True, autopilot_apply_threshold=80)
    _job(db_session, title="Role B", score=95, user=healthy)

    with patch("app.services.autopilot.run_for_user", side_effect=_explode_for_broken):
        totals = autopilot.run_all(db_session)

    assert totals["failed"] == 1
    assert totals["applied"] == 1


# ---------- the receipt ----------

def test_the_actions_endpoint_shows_what_it_did(client, db_session):
    data = register_user(client, email="receipt@example.com")
    headers = auth_headers(data["access_token"])

    user = db_session.query(User).filter(User.email == "receipt@example.com").one()
    job = _job(db_session, title="Some Role")
    db_session.add(AutopilotAction(
        user_id=user.id, job_id=job.id, action="apply", status="done", detail="Applied automatically", fit_score=91
    ))
    db_session.commit()

    resp = client.get("/api/autopilot/actions", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["detail"] == "Applied automatically"


def test_one_users_actions_are_not_visible_to_another(client, db_session):
    mine = register_user(client, email="mine@example.com")
    register_user(client, email="theirs@example.com")

    other = db_session.query(User).filter(User.email == "theirs@example.com").one()
    job = _job(db_session, title="Their Role")
    db_session.add(AutopilotAction(user_id=other.id, job_id=job.id, action="apply", status="done", detail="x"))
    db_session.commit()

    resp = client.get("/api/autopilot/actions", headers=auth_headers(mine["access_token"]))
    assert resp.json() == []
