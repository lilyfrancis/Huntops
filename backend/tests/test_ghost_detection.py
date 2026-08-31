import uuid
from datetime import datetime, timedelta, timezone

from app.models.enums import ExperienceLevel, JobStatus, JobType
from app.models.job import Job
from app.services.ghost_detection import (
    CAUTION_THRESHOLD,
    GHOST_THRESHOLD,
    apply_score,
    classify,
    rescan_all,
    score_job,
)
from tests.conftest import auth_headers, register_user

GOOD_DESCRIPTION = (
    "We are hiring a senior revenue operations manager to own our Salesforce and HubSpot "
    "stack end to end. You will partner with sales leadership on forecasting, build the "
    "reporting layer the exec team runs on, and own our lead routing rules. This is a "
    "newly created seat reporting to the VP of Revenue, with a clear path to lead the "
    "function within two years. We are a 120-person company, Series B, profitable."
)


def make_job(db, **overrides):
    defaults = dict(
        title="Senior RevOps Manager",
        description=GOOD_DESCRIPTION,
        requirements=["Salesforce", "HubSpot"],
        location="Remote",
        salary_range="$120,000–$150,000",
        job_type=JobType.full_time,
        experience_level=ExperienceLevel.senior,
        status=JobStatus.active,
        source="remotive",
        source_url=f"https://example.com/jobs/{uuid.uuid4()}",
        company_name="Flow Corp",
    )
    defaults.update(overrides)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_a_healthy_listing_scores_clean(db_session):
    job = make_job(db_session)
    score, flags = score_job(job, db=db_session)
    assert score < CAUTION_THRESHOLD
    assert classify(score) == "clean"
    assert flags == []


def test_thin_description_and_missing_details_raise_the_score(db_session):
    job = make_job(db_session, description="Sales role. Apply now.", requirements=[], salary_range=None)
    score, flags = score_job(job, db=db_session)
    assert score >= CAUTION_THRESHOLD
    assert "Almost no job description" in flags
    assert "No salary disclosed" in flags
    assert "No requirements listed" in flags


def test_evergreen_talent_pool_ad_is_flagged_as_a_ghost(db_session):
    job = make_job(
        db_session,
        title="General Application — Talent Pool",
        description="Join our talent pipeline! We are always hiring great people. " * 4,
        salary_range=None,
        requirements=[],
    )
    score, flags = score_job(job, db=db_session)
    assert score >= GHOST_THRESHOLD
    assert classify(score) == "likely_ghost"
    assert any("evergreen" in flag for flag in flags)


def test_stale_listings_accrue_score_as_they_age(db_session):
    job = make_job(db_session)
    now = datetime.now(timezone.utc)

    fresh_score, _ = score_job(job, db=db_session, now=now)
    stale_score, stale_flags = score_job(job, db=db_session, now=now + timedelta(days=50))
    ancient_score, ancient_flags = score_job(job, db=db_session, now=now + timedelta(days=120))

    assert fresh_score < stale_score < ancient_score
    assert any("over 45 days" in flag for flag in stale_flags)
    assert any("120 days" in flag for flag in ancient_flags)


def test_anonymous_client_listings_are_flagged(db_session):
    job = make_job(
        db_session,
        description="Our client, a leading fintech, is seeking a RevOps lead. " + GOOD_DESCRIPTION,
    )
    _, flags = score_job(job, db=db_session)
    assert any("not named" in flag for flag in flags)


def test_repeated_reposts_of_the_same_role_raise_the_score(db_session):
    for _ in range(4):
        make_job(db_session)
    job = make_job(db_session)

    score, flags = score_job(job, db=db_session)
    assert any("posted 5 times" in flag for flag in flags)
    assert score >= CAUTION_THRESHOLD


def test_scoring_a_job_before_it_is_persisted_does_not_crash(db_session):
    """Ingestion scores jobs before flush, so created_at and id are still None."""
    job = Job(
        title="Brand New Role",
        description=GOOD_DESCRIPTION,
        requirements=["Python"],
        location="Remote",
        salary_range="$100,000",
        job_type=JobType.full_time,
        experience_level=ExperienceLevel.mid,
        status=JobStatus.active,
        source="remotive",
        source_url="https://example.com/jobs/brand-new",
        company_name="Fresh Co",
    )
    assert job.created_at is None and job.id is None

    score, flags = score_job(job, db=db_session)
    assert score < CAUTION_THRESHOLD
    assert flags == []


def test_apply_score_persists_score_flags_and_timestamp(db_session):
    job = make_job(db_session, description="Too short.", requirements=[], salary_range=None)
    apply_score(db_session, job)
    db_session.commit()
    db_session.refresh(job)

    assert job.ghost_score is not None and job.ghost_score > 0
    assert job.ghost_flags
    assert job.ghost_checked_at is not None


def test_rescan_all_scores_every_job_and_reports_bands(db_session):
    make_job(db_session)
    make_job(db_session, title="Talent Pool", description="Always hiring!", requirements=[], salary_range=None)

    summary = rescan_all(db_session)
    assert summary["scanned"] == 2
    assert summary["clean"] == 1
    assert summary["likely_ghost"] == 1


def test_classify_bands():
    assert classify(None) == "unchecked"
    assert classify(0) == "clean"
    assert classify(CAUTION_THRESHOLD) == "caution"
    assert classify(GHOST_THRESHOLD) == "likely_ghost"


def test_job_feed_exposes_ghost_fields_and_can_hide_ghosts(client, db_session):
    make_job(db_session, title="Real Role")
    ghost = make_job(
        db_session,
        title="Talent Pool — General Application",
        description="Always hiring! Join our talent pipeline.",
        requirements=[],
        salary_range=None,
    )
    rescan_all(db_session)

    all_jobs = client.get("/api/jobs").json()
    assert len(all_jobs) == 2
    assert all("ghost_band" in job and "ghost_flags" in job for job in all_jobs)

    flagged = next(job for job in all_jobs if job["id"] == str(ghost.id))
    assert flagged["ghost_band"] == "likely_ghost"
    assert flagged["ghost_flags"]

    filtered = client.get("/api/jobs", params={"hide_ghosts": True}).json()
    assert [job["title"] for job in filtered] == ["Real Role"]


def test_unscanned_jobs_survive_the_hide_ghosts_filter(client, db_session):
    make_job(db_session, title="Never Scanned")
    filtered = client.get("/api/jobs", params={"hide_ghosts": True}).json()
    assert [job["title"] for job in filtered] == ["Never Scanned"]
    assert filtered[0]["ghost_band"] == "unchecked"


def test_admin_can_trigger_a_rescan(client, db_session):
    make_job(db_session)
    admin = register_user(client, email="ghost-admin@example.com")

    from app.models.enums import UserRole
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ghost-admin@example.com").first()
    user.role = UserRole.admin
    db_session.commit()

    resp = client.post("/api/admin/jobs/rescan-ghosts", headers=auth_headers(admin["access_token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["scanned"] == 1


def test_rescan_endpoint_requires_admin(client):
    seeker = register_user(client, email="ghost-seeker@example.com")
    resp = client.post("/api/admin/jobs/rescan-ghosts", headers=auth_headers(seeker["access_token"]))
    assert resp.status_code == 403
