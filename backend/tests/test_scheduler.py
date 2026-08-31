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


@patch("app.services.scheduler.sync_all_connected_users", side_effect=RuntimeError("gmail api down"))
@patch("app.services.scheduler.notifications.alert_admin")
def test_daily_email_sync_alerts_admin_on_crash(mock_alert, mock_sync):
    scheduler._run_email_sync()
    mock_alert.assert_called_once()


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
