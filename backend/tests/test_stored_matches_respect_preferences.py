"""A score outlives the preferences it was made under.

Scores are kept forever, deliberately: that is what stops the same job being
paid for twice. The consequence nobody designed for is that a job scored
last month — before the user chose a job family, or back when they had
chosen a different one — keeps its score, and anything that reads scores
directly keeps showing it.

Scoring always respected the filters. Display did not, in two places, and
there was no setting on the preferences page that could remove the result.
"""

import uuid

from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.resume import Resume
from app.models.user import User
from app.models.user_preference import UserPreference
from app.services import digest
from tests.conftest import register_user


def _job(db, title, lane) -> Job:
    job = Job(
        title=title, description="d" * 60, requirements=[], location="Lagos, Nigeria",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="test",
        source_url=f"https://x.test/{uuid.uuid4()}", status=JobStatus.active, lane=lane,
    )
    db.add(job)
    db.flush()
    return job


def _scored(db, user_id, job, score=90.0) -> JobMatch:
    match = JobMatch(
        user_id=user_id, job_id=job.id, fit_score=score, skills_score=90,
        experience_score=90, geo_score=50, reason="r",
    )
    db.add(match)
    db.flush()
    return match


def test_the_matches_page_hides_a_lane_the_user_has_since_deselected(client):
    """Reported exactly this way: "I didn't select engineering" — on a page
    showing Senior Web Engineer (React)."""
    from app.db.base import SessionLocal

    data = register_user(client, email="lanes@example.com")
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    user_id = uuid.UUID(data["user"]["id"])

    session = SessionLocal()
    try:
        session.add(Resume(user_id=user_id, raw_text="x", parsed_skills=["Python"], experience_years=4))
        # Scored back when nothing was chosen.
        _scored(session, user_id, _job(session, "Senior Web Engineer (React)", JobLane.engineering))
        _scored(session, user_id, _job(session, "Brand Designer", JobLane.design), score=88.0)
        # Chosen afterwards. Registration already created the row, which is
        # itself the point: the preferences existed before the scores did.
        prefs = session.query(UserPreference).filter(UserPreference.user_id == user_id).one()
        prefs.lanes = ["design", "sales"]
        session.commit()
    finally:
        session.close()

    body = client.get("/api/ai/match-jobs?limit=20", headers=headers).json()

    # Titles come back partly masked — a locked listing shows enough to
    # recognise and not enough to apply behind our back — so this checks the
    # visible stem rather than the whole string.
    assert len(body["matches"]) == 1
    assert body["matches"][0]["job"]["title"].startswith("Brand")
    # The count has to agree with the list, or "1 of 2" invites a Next that
    # leads nowhere.
    assert body["total"] == 1


def test_the_daily_digest_stops_mailing_a_deselected_lane(db_session):
    """Worse than the page, because it arrives unprompted every morning and
    the recipient has no control that would stop it."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    _scored(db_session, user.id, _job(db_session, "Backend Engineer", JobLane.engineering))
    _scored(db_session, user.id, _job(db_session, "Sales Lead", JobLane.sales), score=85.0)
    db_session.add(UserPreference(user_id=user.id, lanes=["sales"]))
    db_session.commit()

    rows = digest.get_top_matches(db_session, user)

    assert [job.title for _match, job in rows] == ["Sales Lead"]


def test_the_digest_still_returns_match_then_job(db_session):
    """Every caller unpacks (match, job). feed_query selects Job first, so
    the rows have to be put back the right way round — a silent swap here
    would render a digest of score objects."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    job = _job(db_session, "Sales Lead", JobLane.sales)
    _scored(db_session, user.id, job, score=85.0)
    db_session.commit()

    (match, returned), = digest.get_top_matches(db_session, user)

    assert isinstance(match, JobMatch) and isinstance(returned, Job)
    assert returned.id == job.id


def test_a_user_with_no_preferences_still_sees_everything(db_session):
    """Empty means no filter here as everywhere else — this must not become
    a way to empty somebody's digest by never onboarding them."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x",
                full_name="Amara Obi", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    _scored(db_session, user.id, _job(db_session, "Backend Engineer", JobLane.engineering))
    db_session.commit()

    assert len(digest.get_top_matches(db_session, user)) == 1
