"""What /match-jobs scores, and what it says when it finds nothing.

Two defects behind "matches keeps saying no matches when there are matches":
the endpoint ignored the user's own filters, unlike the feed, digest and
autopilot; and every failure mode rendered identically to an honest empty
result.
"""

from unittest.mock import patch

import pytest

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType, UserRole
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.models.user_preference import UserPreference
from app.schemas.ai import JobFitScore
from app.services.ai_client import AIResponseError
from tests.conftest import auth_headers, register_user


def _seeker(client, db_session, email="matcher@example.com", **prefs):
    register_user(client, email=email)
    user = db_session.query(User).filter(User.email == email).one()
    db_session.add(Resume(user_id=user.id, raw_text="x", parsed_skills=["Python"], experience_years=5))
    if prefs:
        # Registration already creates the row; this updates it rather than
        # inserting a second one the unique constraint would reject.
        row = db_session.query(UserPreference).filter(UserPreference.user_id == user.id).one_or_none()
        if row is None:
            row = UserPreference(user_id=user.id)
            db_session.add(row)
        for key, value in prefs.items():
            setattr(row, key, value)
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"}).json()
    return user, auth_headers(token["access_token"])


def _job(db_session, title, *, market, lane=JobLane.engineering):
    job = Job(
        title=title, description="d", requirements=[], location=market,
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="email-linkedin", source_url=f"https://x.test/{title}",
        status=JobStatus.active, market=market, lane=lane, company_name="Acme",
    )
    db_session.add(job)
    db_session.commit()
    return job


def _score(value, index=0):
    return JobFitScore(
        job_index=index, overall_score=value, skills_score=value,
        experience_score=value, location_score=value, reason="because",
    )


def test_scoring_only_sees_jobs_that_pass_the_users_filters(client, db_session):
    """The feed, digest and autopilot all filter by preferences. This
    endpoint queried every active job, so it spent AI calls on markets the
    user had excluded — and those could crowd out the ones they wanted."""
    _job(db_session, "Nigerian Engineer", market="Nigeria")
    _job(db_session, "Canadian Engineer", market="Canada")
    _user, headers = _seeker(client, db_session, target_markets=["Nigeria"])

    with patch("app.services.matching.score_jobs") as score:
        score.side_effect = lambda resume, jobs, market: [(j, _score(90, i), False) for i, j in enumerate(jobs)]
        resp = client.get("/api/ai/match-jobs", headers=headers)

    assert resp.status_code == 200
    sent_for_scoring = [j.title for j in score.call_args.args[1]]
    assert sent_for_scoring == ["Nigerian Engineer"]
    assert resp.json()["candidates_scored"] == 1


def test_no_candidates_is_reported_separately_from_nothing_good_enough(client, db_session):
    """Different problems, different fixes: widen your filters, versus the
    roles coming in genuinely do not suit you."""
    _job(db_session, "Canadian Engineer", market="Canada")
    _user, headers = _seeker(client, db_session, target_markets=["Nigeria"])

    with patch("app.services.matching.score_jobs") as score:
        body = client.get("/api/ai/match-jobs", headers=headers).json()

    score.assert_not_called()          # nothing to score, so no AI call, so no charge
    assert body["candidates_scored"] == 0
    assert body["matches"] == []


def test_scored_but_below_the_bar_reports_how_many_and_what_the_bar_was(client, db_session):
    _job(db_session, "Nigerian Engineer", market="Nigeria")
    _job(db_session, "Another Nigerian Role", market="Nigeria")
    _user, headers = _seeker(client, db_session, target_markets=["Nigeria"])

    with patch("app.services.matching.score_jobs") as score:
        score.side_effect = lambda resume, jobs, market: [(j, _score(20, i), False) for i, j in enumerate(jobs)]
        body = client.get("/api/ai/match-jobs", headers=headers).json()

    assert body["matches"] == []
    assert body["candidates_scored"] == 2
    assert body["threshold"] == 50


def test_a_scoring_failure_is_an_error_not_an_empty_result(client, db_session):
    """The page rendered a 502 as "No strong matches yet", which sent people
    off to rewrite a résumé that was never the problem."""
    _job(db_session, "Nigerian Engineer", market="Nigeria")
    _user, headers = _seeker(client, db_session, target_markets=["Nigeria"])

    with patch("app.services.matching.score_jobs", side_effect=AIResponseError("model unavailable")):
        resp = client.get("/api/ai/match-jobs", headers=headers)

    assert resp.status_code == 502
    assert "model unavailable" in resp.json()["detail"]


def test_a_user_with_no_preferences_still_sees_everything(client, db_session):
    """An untouched preferences row must not mean an empty feed."""
    _job(db_session, "Nigerian Engineer", market="Nigeria")
    _job(db_session, "Canadian Engineer", market="Canada")
    _user, headers = _seeker(client, db_session)

    with patch("app.services.matching.score_jobs") as score:
        score.side_effect = lambda resume, jobs, market: [(j, _score(90, i), False) for i, j in enumerate(jobs)]
        body = client.get("/api/ai/match-jobs", headers=headers).json()

    assert body["candidates_scored"] == 2
    assert len(body["matches"]) == 2


def test_a_user_with_no_resume_is_told_so_rather_than_shown_nothing(client, db_session):
    register_user(client, email="noresume@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "noresume@example.com", "password": "StrongPass1"}).json()
    resp = client.get("/api/ai/match-jobs", headers=auth_headers(token["access_token"]))

    assert resp.status_code == 404
    assert "résumé" in resp.json()["detail"]
