from unittest.mock import patch

from app.models.enums import ExperienceLevel, JobStatus, JobType, UserRole
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.ai import JobFitScore
from app.services import scheduler


def test_start_scheduler_noop_in_test_environment():
    assert scheduler.start_scheduler() is None


@patch("app.services.scheduler.ingest_all", side_effect=RuntimeError("db exploded"))
@patch("app.services.scheduler.notifications.alert_admin")
def test_daily_aggregation_alerts_admin_on_crash(mock_alert, mock_ingest):
    scheduler._run_daily_aggregation()
    mock_alert.assert_called_once()
    assert "aggregation" in mock_alert.call_args[0][0].lower()


@patch("app.services.scheduler.sync_all_mailboxes", side_effect=RuntimeError("gmail api down"))
@patch("app.services.scheduler.notifications.alert_admin")
def test_daily_email_sync_alerts_admin_on_crash(mock_alert, mock_sync):
    scheduler._run_email_sync()
    mock_alert.assert_called_once()


@patch("app.services.scheduler.notifications.alert_admin")
def test_daily_email_sync_alerts_admin_when_a_single_mailbox_fails(mock_alert):
    """A mailbox that stops syncing is a market whose feed quietly stops
    filling — the run "succeeds" and nobody finds out until users complain."""
    failure = {
        "mailbox": "alerts-uk@huntops.site", "market": "UK", "status": "error",
        "fetched": 0, "extracted": 0, "inserted": 0, "error": "invalid_grant",
    }
    ok = {
        "mailbox": "alerts-ca@huntops.site", "market": "Canada", "status": "success",
        "fetched": 3, "extracted": 5, "inserted": 5, "error": None,
    }
    with patch("app.services.scheduler.sync_all_mailboxes", return_value=[failure, ok]):
        scheduler._run_email_sync()

    mock_alert.assert_called_once()
    assert "invalid_grant" in mock_alert.call_args[0][1]


@patch("app.services.scheduler.notifications.alert_admin")
def test_daily_email_sync_stays_quiet_when_every_mailbox_is_healthy(mock_alert):
    healthy = {
        "mailbox": "alerts-ca@huntops.site", "market": "Canada", "status": "success",
        "fetched": 3, "extracted": 5, "inserted": 5, "error": None,
    }
    with patch("app.services.scheduler.sync_all_mailboxes", return_value=[healthy]):
        scheduler._run_email_sync()

    mock_alert.assert_not_called()


def test_daily_digest_scores_persists_and_sends(db_session):
    user = User(email="digest-user@example.com", password_hash="x", full_name="X", role=UserRole.job_seeker)
    db_session.add(user)
    db_session.flush()
    db_session.add(Resume(user_id=user.id, raw_text="dummy", parsed_skills=["Python"]))
    job = Job(
        title="Backend Role", description="d", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="remotive", source_url="https://example.com/scheduler-job", status=JobStatus.active,
    )
    db_session.add(job)
    db_session.commit()

    fake_score = [(job, JobFitScore(job_index=0, overall_score=80, skills_score=80, experience_score=80, location_score=80, reason="great"), False)]

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.matching.score_jobs", return_value=fake_score), \
         patch("app.services.scheduler.notifications.send_email", return_value=True) as mock_send:
        scheduler._run_daily_digest()

    mock_send.assert_called_once()
    call_args = mock_send.call_args[0]
    assert call_args[0] == "digest-user@example.com"

    from app.models.job_match import JobMatch
    match = db_session.query(JobMatch).filter(JobMatch.user_id == user.id, JobMatch.job_id == job.id).first()
    assert match is not None
    assert match.fit_score == 80


def test_daily_digest_skips_user_on_ai_failure_without_crashing(db_session):
    from app.services.ai_client import AIResponseError

    user = User(email="digest-fail@example.com", password_hash="x", full_name="X", role=UserRole.job_seeker)
    db_session.add(user)
    db_session.flush()
    db_session.add(Resume(user_id=user.id, raw_text="dummy", parsed_skills=["Python"]))
    job = Job(
        title="Role", description="d", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
        source="remotive", source_url="https://example.com/scheduler-job-2", status=JobStatus.active,
    )
    db_session.add(job)
    db_session.commit()

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.matching.score_jobs", side_effect=AIResponseError("bad json")), \
         patch("app.services.scheduler.notifications.send_email") as mock_send, \
         patch("app.services.scheduler.notifications.alert_admin") as mock_alert:
        scheduler._run_daily_digest()

    mock_send.assert_not_called()
    mock_alert.assert_not_called()  # a single user's AI failure isn't a crash worth paging on


# ---------- the digest goes to whichever channel the user chose ----------

def _seeker_with_a_match(session, email, *, channel, number=None):
    from app.models.job_match import JobMatch
    from app.models.user_preference import UserPreference

    user = User(email=email, password_hash="x", full_name="Amara Obi",
                role=UserRole.job_seeker, whatsapp_number=number)
    session.add(user)
    session.flush()
    session.add(Resume(user_id=user.id, raw_text="dummy", parsed_skills=["Python"]))
    session.add(UserPreference(user_id=user.id, digest_channel=channel))

    job = Job(title="Growth Lead", description="d", requirements=[], location="Remote",
              job_type=JobType.full_time, experience_level=ExperienceLevel.mid,
              source="internal", source_url=f"https://example.com/{email}", status=JobStatus.active,
              company_name="Shopify")
    session.add(job)
    session.flush()
    session.add(JobMatch(user_id=user.id, job_id=job.id, fit_score=91))
    session.commit()
    return user


def _run_digest_with_stubbed_scoring():
    """Scoring is an AI call; this exercises delivery, not matching."""
    with patch("app.services.scheduler.matching.score_jobs", return_value=[]), \
         patch("app.services.scheduler.matching.persist_matches", return_value=[]):
        scheduler._run_daily_digest()


@patch("app.services.scheduler.whatsapp.send_template", return_value=True)
@patch("app.services.scheduler.notifications.send_email", return_value=True)
def test_an_email_user_gets_no_whatsapp(mock_email, mock_whatsapp, db_session):
    _seeker_with_a_match(db_session, "email-only@example.com", channel="email", number="+2348031234567")
    _run_digest_with_stubbed_scoring()

    mock_email.assert_called_once()
    mock_whatsapp.assert_not_called()


@patch("app.services.scheduler.whatsapp.send_template", return_value=True)
@patch("app.services.scheduler.notifications.send_email", return_value=True)
def test_a_whatsapp_user_gets_no_email(mock_email, mock_whatsapp, db_session):
    _seeker_with_a_match(db_session, "wa-only@example.com", channel="whatsapp", number="+2348031234567")
    _run_digest_with_stubbed_scoring()

    mock_whatsapp.assert_called_once()
    mock_email.assert_not_called()


@patch("app.services.scheduler.whatsapp.send_template", return_value=True)
@patch("app.services.scheduler.notifications.send_email", return_value=True)
def test_choosing_whatsapp_without_giving_a_number_falls_back_to_nothing(mock_email, mock_whatsapp, db_session):
    """No number means no message — silently emailing them instead would
    ignore a preference they explicitly set."""
    _seeker_with_a_match(db_session, "wa-nonumber@example.com", channel="whatsapp", number=None)
    _run_digest_with_stubbed_scoring()

    mock_whatsapp.assert_not_called()
    mock_email.assert_not_called()


@patch("app.services.scheduler.whatsapp.send_template", return_value=True)
@patch("app.services.scheduler.notifications.send_email", return_value=True)
def test_both_means_both(mock_email, mock_whatsapp, db_session):
    _seeker_with_a_match(db_session, "wa-both@example.com", channel="both", number="+2348031234567")
    _run_digest_with_stubbed_scoring()

    mock_email.assert_called_once()
    mock_whatsapp.assert_called_once()


@patch("app.services.scheduler.whatsapp.send_template", return_value=True)
@patch("app.services.scheduler.notifications.send_email", return_value=True)
def test_opting_out_stops_both(mock_email, mock_whatsapp, db_session):
    _seeker_with_a_match(db_session, "wa-none@example.com", channel="none", number="+2348031234567")
    _run_digest_with_stubbed_scoring()

    mock_email.assert_not_called()
    mock_whatsapp.assert_not_called()
