import uuid
from datetime import datetime, timedelta, timezone

from app.models.application import Application
from app.models.enums import (
    ApplicationStatus,
    ExperienceLevel,
    InterviewStatus,
    JobStatus,
    JobType,
    OutreachStatus,
)
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.user import User
from app.services.stats import _streaks, build_stats
from tests.conftest import auth_headers, register_user


def _make_job(db, title="Stats Role"):
    job = Job(
        title=title,
        description="A description long enough to pass validation checks.",
        requirements=["Python"],
        location="Remote",
        job_type=JobType.full_time,
        experience_level=ExperienceLevel.mid,
        status=JobStatus.active,
        source="remotive",
        source_url=f"https://example.com/{uuid.uuid4()}",
        company_name="Stats Corp",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_application(db, user, job, status, created_at=None):
    app_row = Application(
        job_id=job.id,
        candidate_id=user.id,
        candidate_name=user.full_name,
        candidate_email=user.email,
        status=status,
    )
    if created_at:
        app_row.created_at = created_at
    db.add(app_row)
    db.commit()
    return app_row


def _seeker(client, db_session, email="stats@example.com"):
    register_user(client, email=email)
    return db_session.query(User).filter(User.email == email).first()


# ---------- streak arithmetic (pure, so tested directly) ----------

def test_streak_counts_consecutive_days_up_to_today():
    today = datetime(2026, 8, 31).date()
    active = [today - timedelta(days=n) for n in (4, 2, 1, 0)]
    current, longest = _streaks(sorted(active), today)
    assert current == 3  # today, yesterday, day before
    assert longest == 3


def test_streak_survives_a_day_that_has_not_happened_yet():
    """Ending yesterday keeps the run live — opening the app in the morning
    must not show a streak that already looks broken."""
    today = datetime(2026, 8, 31).date()
    active = sorted([today - timedelta(days=n) for n in (3, 2, 1)])
    current, longest = _streaks(active, today)
    assert current == 3
    assert longest == 3


def test_streak_is_zero_once_the_run_is_actually_broken():
    today = datetime(2026, 8, 31).date()
    active = sorted([today - timedelta(days=n) for n in (10, 9, 8)])
    current, longest = _streaks(active, today)
    assert current == 0
    assert longest == 3


def test_longest_streak_survives_a_later_gap():
    today = datetime(2026, 8, 31).date()
    active = sorted([today - timedelta(days=n) for n in (20, 19, 18, 17, 5, 0)])
    current, longest = _streaks(active, today)
    assert current == 1
    assert longest == 4


def test_no_activity_means_no_streak():
    assert _streaks([], datetime(2026, 8, 31).date()) == (0, 0)


# ---------- funnel ----------

def test_funnel_is_cumulative_so_later_stages_never_exceed_earlier_ones(client, db_session):
    user = _seeker(client, db_session)
    job = _make_job(db_session)

    _make_application(db_session, user, _make_job(db_session, "A"), ApplicationStatus.pending)
    _make_application(db_session, user, _make_job(db_session, "B"), ApplicationStatus.reviewed)
    _make_application(db_session, user, _make_job(db_session, "C"), ApplicationStatus.interviewing)
    _make_application(db_session, user, job, ApplicationStatus.offered)

    stats = build_stats(db_session, user)
    counts = {row["stage"]: row["count"] for row in stats["funnel"]}

    assert counts["applied"] == 4
    assert counts["reviewed"] == 3  # reviewed + interviewing + offered
    assert counts["interviewing"] == 2
    assert counts["offered"] == 1

    ordered = [row["count"] for row in stats["funnel"]]
    assert ordered == sorted(ordered, reverse=True)


def test_rejected_applications_count_as_applied_only(client, db_session):
    user = _seeker(client, db_session)
    _make_application(db_session, user, _make_job(db_session), ApplicationStatus.rejected)

    counts = {row["stage"]: row["count"] for row in build_stats(db_session, user)["funnel"]}
    assert counts["applied"] == 1
    assert counts["reviewed"] == 0


def test_conversion_rates_are_none_with_no_applications(client, db_session):
    user = _seeker(client, db_session)
    conversion = build_stats(db_session, user)["conversion"]
    assert conversion["applied_to_interviewing"] is None
    assert conversion["applied_to_offered"] is None


def test_conversion_rates_are_computed_from_the_funnel(client, db_session):
    user = _seeker(client, db_session)
    for status in (ApplicationStatus.pending, ApplicationStatus.pending, ApplicationStatus.interviewing, ApplicationStatus.offered):
        _make_application(db_session, user, _make_job(db_session, str(uuid.uuid4())), status)

    conversion = build_stats(db_session, user)["conversion"]
    assert conversion["applied_to_interviewing"] == 0.5  # 2 of 4
    assert conversion["applied_to_offered"] == 0.25


# ---------- totals & activity ----------

def test_totals_count_only_this_users_records(client, db_session):
    user = _seeker(client, db_session)
    other = _seeker(client, db_session, email="other@example.com")
    job = _make_job(db_session)

    _make_application(db_session, user, job, ApplicationStatus.pending)
    _make_application(db_session, other, _make_job(db_session, "Other"), ApplicationStatus.pending)

    db_session.add(Outreach(user_id=user.id, job_id=job.id, status=OutreachStatus.sent))
    db_session.add(Outreach(user_id=user.id, job_id=_make_job(db_session, "D").id, status=OutreachStatus.failed))
    db_session.add(InterviewSession(user_id=user.id, role_title="X", status=InterviewStatus.completed))
    db_session.add(InterviewSession(user_id=user.id, role_title="Y", status=InterviewStatus.in_progress))
    db_session.commit()

    totals = build_stats(db_session, user)["totals"]
    assert totals["applications"] == 1
    assert totals["outreach_sent"] == 1  # failed outreach is not "sent"
    assert totals["interviews_completed"] == 1  # in-progress doesn't count


def test_activity_window_is_a_full_grid_ending_today(client, db_session):
    user = _seeker(client, db_session)
    stats = build_stats(db_session, user)
    activity = stats["activity"]

    assert len(activity) == stats["streak"]["window_days"] == 56
    assert activity[-1]["date"] == datetime.now(timezone.utc).date().isoformat()
    assert all(day["active"] is False for day in activity)


def test_activity_marks_days_the_user_actually_did_something(client, db_session):
    user = _seeker(client, db_session)
    today = datetime.now(timezone.utc)
    _make_application(db_session, user, _make_job(db_session), ApplicationStatus.pending, created_at=today)

    stats = build_stats(db_session, user)
    assert stats["activity"][-1]["active"] is True
    assert stats["streak"]["current_days"] == 1
    assert stats["streak"]["active_days_in_window"] == 1


# ---------- endpoint ----------

def test_stats_endpoint_returns_the_full_shape(client, db_session):
    seeker = register_user(client, email="stats-endpoint@example.com")
    resp = client.get("/api/stats/me", headers=auth_headers(seeker["access_token"]))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [row["stage"] for row in body["funnel"]] == ["applied", "reviewed", "interviewing", "offered"]
    assert set(body["totals"]) == {"matches_scored", "applications", "outreach_sent", "interviews_completed"}
    assert body["streak"]["current_days"] == 0
    assert len(body["activity"]) == 56


def test_stats_endpoint_requires_a_job_seeker(client, db_session):
    employer = register_user(client, email="stats-employer@example.com", role="employer", company_name="X")
    resp = client.get("/api/stats/me", headers=auth_headers(employer["access_token"]))
    assert resp.status_code == 403
